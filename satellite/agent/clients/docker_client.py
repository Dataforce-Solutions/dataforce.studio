import asyncio
import contextlib
import logging
from collections.abc import Iterable
from typing import Any, Self
from uuid import UUID

import aiodocker
from aiodocker.containers import DockerContainer
from aiodocker.exceptions import DockerError

from agent._exceptions import ContainerNotFoundError, ContainerNotRunningError
from agent.settings import config as config_settings

logger = logging.getLogger(__name__)

MODEL_CACHE_MOUNT = "/app/models"
MODEL_CACHE_VOLUME_PREFIX = "satellite-model-cache-"

# shared volume of the pre-per-artifact design; nothing mounts it any more
LEGACY_MODEL_CACHE_VOLUME = "satellite-models-cache"


def model_cache_volume(model_id: str) -> str:
    return f"{MODEL_CACHE_VOLUME_PREFIX}{model_id}"


# network alias declared in docker-compose, not the container or service name
AGENT_HOST = "satellite-agent"

# aged by the newest path in the tree — the staging root's own mtime freezes
# once tar creates its top-level entry
STALE_STAGING_MINUTES = 180


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

    # a daemon hiccup while inspecting a container is retried this many times, a second apart
    INSPECT_ATTEMPTS = 3

    async def check_container_running(self, deployment_id: str) -> dict[str, str]:
        """Raise unless the deployment's container is running; return its labels.

        Only a 404 means the container is not there. Any other answer from the daemon —
        a 5xx, a timeout — says nothing about the container, and callers act on
        "not found" (recreating, or giving up a wait), so it is retried and then raised
        as the Docker error it is.
        """
        for attempt in range(1, self.INSPECT_ATTEMPTS + 1):
            try:
                container = await self.client.containers.get(f"sat-{deployment_id}")
                # the container can be removed between the lookup and this read
                container_info = await container.show()
                break
            except DockerError as e:
                if e.status == 404:
                    raise ContainerNotFoundError(deployment_id) from e
                if attempt == self.INSPECT_ATTEMPTS:
                    raise
                logger.warning(
                    f"[DockerService] inspecting 'sat-{deployment_id}' failed "
                    f"(attempt {attempt}/{self.INSPECT_ATTEMPTS}): {e}"
                )
                await asyncio.sleep(1)

        status = container_info["State"]["Status"]

        if status != "running":
            raise ContainerNotRunningError(deployment_id, status)

        return container_info.get("Config", {}).get("Labels") or {}

    async def cleanup_stale_staging(self, keep_artifacts: Iterable[str] = ()) -> None:
        """Reclaim unused cache volumes and abandoned `.partial` staging directories.

        Volumes of ``keep_artifacts`` are never deleted, whatever their reference
        count says this instant: container replacement is delete-then-create, and
        inside that gap a warm cache is momentarily referenced by nobody.
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
        keep = {model_cache_volume(str(artifact)) for artifact in keep_artifacts if artifact}

        still_in_use: list[str] = []
        for name in candidates:
            if name in keep:
                still_in_use.append(name)
                continue
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

        # removed only when nothing inside was touched for STALE_STAGING_MINUTES —
        # the root's own mtime would read a live unpack as abandoned
        sweep_script = (
            "for d in /sweep/*/.*.partial; do "
            '[ -d "$d" ] || continue; '
            f'if [ -z "$(find "$d" -mmin -{STALE_STAGING_MINUTES} -print -quit)" ]; '
            'then rm -rf "$d"; fi; '
            "done"
        )
        try:
            container = await self._run_cache_container(
                cmd=["sh", "-c", sweep_script],
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
