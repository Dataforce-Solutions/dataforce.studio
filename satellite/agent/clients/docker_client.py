import contextlib
import logging
from typing import Any, Self
from uuid import UUID

import aiodocker
from aiodocker.containers import DockerContainer
from aiodocker.exceptions import DockerError

from agent._exceptions import ContainerNotFoundError, ContainerNotRunningError
from agent.settings import config as config_settings

logger = logging.getLogger(__name__)

# Where a model container finds its extracted model. What is mounted there is a volume
# private to the artifact: deployments of the same artifact share one copy, and no
# deployment can see — or poison — the cache of any other. The volume is the isolation
# boundary; one shared read-write volume for everyone was the old design's mistake.
MODEL_CACHE_MOUNT = "/app/models"
MODEL_CACHE_VOLUME_PREFIX = "satellite-model-cache-"

# The single shared volume of the pre-per-artifact design. Nothing mounts it any more; the
# stale-cache sweep deletes it as soon as the last legacy container referencing it is gone.
LEGACY_MODEL_CACHE_VOLUME = "satellite-models-cache"


def model_cache_volume(model_id: str) -> str:
    return f"{MODEL_CACHE_VOLUME_PREFIX}{model_id}"


# The hostname model containers reach the Agent by. It is a network alias declared in
# docker-compose, not the container or service name: those are "satellite-agent-1" and
# "agent", and neither is stable enough to hard-code here.
AGENT_HOST = "satellite-agent"

# How old a `.partial` staging directory must be before the sweep may assume the unpack
# that created it is dead rather than slow. Unpacking takes minutes; an hour is margin.
STALE_STAGING_MINUTES = 60


class DockerService:
    def __init__(self) -> None:
        self.client = aiodocker.Docker()
        self.network_name = "satellite_satellite-network"

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001, ANN201
        await self.client.close()

    async def run_model_container(
        self,
        *,
        image: str,
        name: str,
        model_id: str,
        container_port: int = config_settings.MODEL_SERVER_PORT,
        labels: dict[str, str] | None = None,
        env: dict[str, str] | None = None,
        restart: str = "on-failure",
    ) -> DockerContainer:
        base_env = dict(env or {})
        # the Agent's port, not the model server's — this address is where the container
        # calls back to, not where it listens. Applied last on purpose: a container that
        # could point it elsewhere would send its artifact token to that elsewhere.
        agent_url = f"http://{AGENT_HOST}:{config_settings.AGENT_PORT}"
        if base_env.get("SATELLITE_AGENT_URL") not in (None, agent_url):
            logger.warning(
                f"[DockerService] Ignoring caller-supplied SATELLITE_AGENT_URL for '{name}'."
            )
        base_env["SATELLITE_AGENT_URL"] = agent_url

        config: dict[str, Any] = {
            "Image": image,
            "Labels": labels or {},
            "ExposedPorts": {f"{container_port}/tcp": {}},
            "Env": [f"{k}={v}" for k, v in base_env.items()],
            "HostConfig": {
                "RestartPolicy": {"Name": restart, "MaximumRetryCount": 3},
                "NetworkMode": self.network_name,
                # The extracted model lives on a volume, not in the container's own layer:
                # the artifact URL is presigned and expires long before the container does,
                # so a restart that had to re-download would never come back up. The volume
                # is named after the artifact, so this container sees no other's cache.
                "Binds": [f"{model_cache_volume(model_id)}:{MODEL_CACHE_MOUNT}"],
            },
        }

        container = await self.client.containers.create_or_replace(config=config, name=name)
        await container.start()

        return container

    async def remove_model_container(self, *, deployment_id: UUID) -> tuple[bool, str | None]:
        container_name = f"sat-{deployment_id}"
        try:
            container = await self.client.containers.get(container_name)
        except DockerError:
            return False, None

        info = await container.show()
        labels = info.get("Config", {}).get("Labels", {})
        model_id = labels.get("df.model_id")

        with contextlib.suppress(DockerError):
            await container.stop()

        with contextlib.suppress(DockerError):
            await container.delete(force=True)

        return True, model_id

    async def is_model_in_use(self, model_id: str) -> bool:
        containers = await self.client.containers.list(all=True)
        for container in containers:
            info = await container.show()
            labels = info.get("Config", {}).get("Labels", {})
            if labels.get("df.model_id") == model_id:
                return True
        return False

    async def _run_cache_container(self, *, cmd: list[str], binds: list[str]) -> DockerContainer:
        """Run one command against model cache volumes and wait for it to finish.

        The caches live on named volumes, not on the Agent's own filesystem, so the only
        way to touch their contents is through a container that mounts them.
        """
        image_name = "alpine:latest"

        try:
            await self.client.images.get(image_name)
        except DockerError:
            logger.info("[DockerService] Pulling alpine:latest image...")
            await self.client.images.pull(image_name)

        config: dict[str, Any] = {
            "Image": image_name,
            "Cmd": cmd,
            "HostConfig": {
                "Binds": binds,
            },
        }
        container = await self.client.containers.create(config=config)
        await container.start()
        await container.wait()

        return container

    async def check_container_running(self, deployment_id: str) -> dict[str, str]:
        """Raise unless the deployment's container is running; return its labels.

        The labels ride along because the caller that cares whether a container runs is
        the same one that must judge which Agent launched it, and the inspection already
        happened here.
        """
        try:
            container = await self.client.containers.get(f"sat-{deployment_id}")
        except DockerError as e:
            raise ContainerNotFoundError(deployment_id) from e

        container_info = await container.show()
        status = container_info["State"]["Status"]

        if status != "running":
            raise ContainerNotRunningError(deployment_id, status)

        return container_info.get("Config", {}).get("Labels") or {}

    async def cleanup_stale_staging(self) -> None:
        """Reclaim cache volumes and staging directories nothing will ever use again.

        Whole volumes go first: an undeploy that died before its own cleanup leaves the
        artifact's volume behind, and no later task will ask about that artifact again.
        Docker refuses to delete a volume any container still references, so the deletion
        attempt doubles as the in-use check. The volumes that refuse are alive, and inside
        them only `.partial` staging directories abandoned by a hard-killed unpack are
        swept — no later start removes those either, staging paths being unique per
        attempt. Only age tells such an orphan apart from an unpack still in flight, so
        only directories old enough that no live unpack can still own them are removed.
        """
        try:
            listed = await self.client.volumes.list()
        except DockerError as error:
            logger.error(f"[DockerService] Could not list cache volumes.\n{error}")
            return

        names = [v.get("Name", "") for v in listed.get("Volumes") or []]
        candidates = [
            name
            for name in names
            if name.startswith(MODEL_CACHE_VOLUME_PREFIX) or name == LEGACY_MODEL_CACHE_VOLUME
        ]

        still_in_use: list[str] = []
        for name in candidates:
            try:
                volume = await self.client.volumes.get(name)
                await volume.delete()
                logger.info(f'[DockerService] Removed unused model cache volume "{name}".')
            except DockerError as error:
                if error.status == 409:
                    still_in_use.append(name)
                elif error.status != 404:  # 404: gone between listing and deleting
                    logger.error(f'[DockerService] Could not remove volume "{name}".\n{error}')

        if not still_in_use:
            return

        try:
            container = await self._run_cache_container(
                cmd=[
                    "find",
                    "/sweep",
                    "-mindepth",
                    "2",
                    "-maxdepth",
                    "2",
                    "-name",
                    ".*.partial",
                    "-mmin",
                    f"+{STALE_STAGING_MINUTES}",
                    "-exec",
                    "rm",
                    "-rf",
                    "{}",
                    "+",
                ],
                binds=[f"{name}:/sweep/{name}" for name in still_in_use],
            )

            with contextlib.suppress(DockerError):
                await container.delete(force=True)
        except Exception as error:
            logger.error(f"[DockerService] Error cleaning stale staging directories.\n{error}")

    async def cleanup_model_cache(self, model_id: str) -> None:
        """Delete the artifact's cache volume once no container uses the model any more."""
        if await self.is_model_in_use(model_id):
            logger.info(
                f'[DockerService] Model "{model_id}" is still in use, skipping cache cleanup.'
            )
            return

        try:
            volume = await self.client.volumes.get(model_cache_volume(model_id))
            await volume.delete()
            logger.info(f'[DockerService] Successfully cleaned cache for model "{model_id}".')
        except DockerError as error:
            if error.status == 404:  # never cached on this Satellite — nothing to reclaim
                return
            logger.error(f"[DockerService] Error cleaning model cache.\n{str(error)}")
