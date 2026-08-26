import asyncio
import logging
from collections.abc import Callable
from contextlib import suppress
from typing import Any
from uuid import UUID

from agent._exceptions import (
    ContainerNotFoundError,
    ContainerNotRunningError,
    DeploymentNotHostedError,
)
from agent.clients import ModelServerClient, ModelServerError, PlatformClient
from agent.clients.docker_client import DockerService
from agent.handlers.container_launcher import (
    LAUNCHER_PROTOCOL,
    LAUNCHER_PROTOCOL_LABEL,
    launch_model_container,
)
from agent.monitoring.instrumentation import InferenceInstrumentation
from agent.monitoring.telemetry import TelemetrySetup
from agent.schemas import (
    Deployment,
    DeploymentMetadata,
    DeploymentStatus,
    DeploymentUpdate,
    LocalDeployment,
    Secret,
    gate_reference_profile,
    monitoring_url_for_deployment,
)
from agent.schemas.deployments import ErrorMessage
from agent.settings import config

logger = logging.getLogger(__name__)

# What a recovery writes into the deployment's error message while the relaunched container
# boots. The next reconciliation reads it back to tell a container that is still warming up
# from one that is genuinely wedged — the Agent that started the wait may not live to
# finish it, and this marker is all that survives.
RECOVERING_REASON = "Recovering"


class ModelServerHandler:
    # How long a relaunched container may take to download its model, build its environment
    # and answer, when the deployment does not state its own timeout.
    recovery_health_check_timeout = 1800

    def __init__(self, telemetry: TelemetrySetup | None = None) -> None:
        self.deployments: dict[str, LocalDeployment] = {}
        self._openapi_cache_invalidation_callbacks: list[Callable] = []
        self._telemetry = telemetry
        self._instrumentation: InferenceInstrumentation | None = None
        if telemetry and telemetry.active:
            self._instrumentation = InferenceInstrumentation(telemetry)

    async def add_single_deployment(
        self,
        deployment_id: str,
        dynamic_attributes_secrets: dict[str, str] | None,
        *,
        monitoring_enabled: bool = False,
        metadata: DeploymentMetadata | None = None,
    ) -> None:
        manifest = None
        openapi_schema = None
        reference_profile = None
        try:
            async with ModelServerClient() as client:
                manifest = await client.get_manifest(deployment_id)
                openapi_schema = await client.get_openapi_schema(deployment_id)
                reference_profile = await client.get_reference_profile(deployment_id)
        except Exception as e:
            logger.warning(
                f"[add_single_deployment] Could not fetch manifest/schema for {deployment_id}: {e}"
            )

        reference_profile, profile_status = gate_reference_profile(manifest, reference_profile)

        self.deployments[deployment_id] = LocalDeployment(
            deployment_id=deployment_id,
            dynamic_attributes_secrets=dynamic_attributes_secrets,
            manifest=manifest,
            openapi_schema=openapi_schema,
            monitoring_enabled=monitoring_enabled,
            reference_profile=reference_profile,
            profile_status=profile_status,
            metadata=metadata or DeploymentMetadata(),
        )

    @staticmethod
    def _read_monitoring_enabled(monitoring_mode: str | None) -> bool:
        return (monitoring_mode or "off").strip().lower() == "full"

    async def add_deployment(self, deployment: Deployment) -> None:
        monitoring_enabled = self._read_monitoring_enabled(deployment.monitoring_mode)
        await self.add_single_deployment(
            deployment.id,
            deployment.dynamic_attributes_secrets,
            monitoring_enabled=monitoring_enabled,
            metadata=DeploymentMetadata.from_platform(deployment.model_dump()),
        )
        self._invalidate_openapi_cache()

    async def remove_deployment(self, deployment_id: UUID) -> None:
        self.deployments.pop(str(deployment_id), None)
        self._invalidate_openapi_cache()

    async def get_deployment(self, deployment_id: str) -> LocalDeployment | None:
        return self.deployments.get(deployment_id)

    async def list_active_deployments(self) -> list[LocalDeployment]:
        active_deployments = {}

        for dep_id, info in self.deployments.items():
            async with ModelServerClient() as client:
                with suppress(Exception):
                    health_ok = await client.is_healthy(dep_id)
                    if health_ok:
                        active_deployments[dep_id] = info

        self.deployments = active_deployments
        return list(active_deployments.values())

    async def _relaunch(
        self,
        docker: DockerService,
        platform: PlatformClient,
        deployment_id: str,
        reason: str,
    ) -> bool:
        """Recreate a deployment's model container under the current launch contract.

        Two kinds of container end up here: stopped ones, which can never simply be started
        again — a legacy container would try to download its model from a presigned link
        that expired hours ago and die — and running legacy ones, which are one restart away
        from the same death. Recreating is the only way forward, and the Platform record
        says this deployment is supposed to be serving.
        """
        logger.info(f"[ModelServerHandler] relaunching '{deployment_id}': {reason}")
        try:
            deployment = await platform.get_deployment(UUID(deployment_id))
            if deployment is None:
                raise ValueError("deployment not found on the Platform")
            await launch_model_container(platform, docker, deployment)
        except Exception as error:
            logger.warning(f"[ModelServerHandler] relaunch of '{deployment_id}' failed: {error}")
            await platform.update_deployment(
                deployment_id,
                DeploymentUpdate(
                    status=DeploymentStatus.NOT_RESPONDING,
                    error_message={"reason": reason, "error": f"Relaunch failed: {error}"},
                ),
            )
            return False

        # Still `not_responding`, not `pending`, while the relaunched container boots.
        # `pending` belongs to deploy tasks, and reconciliation skips it on that assumption
        # — a deployment parked there by a recovery the Agent did not live to finish would
        # be skipped forever. `not_responding` is re-examined on every start, so an
        # interrupted recovery is picked up by the next one.
        await platform.update_deployment(
            deployment_id,
            DeploymentUpdate(
                status=DeploymentStatus.NOT_RESPONDING,
                error_message={
                    "reason": RECOVERING_REASON,
                    "error": f"Container was relaunched and is starting up: {reason}",
                },
            ),
        )
        return True

    async def _settle_recovered(
        self, docker: DockerService, platform: PlatformClient, dep: dict[str, Any]
    ) -> None:
        """Wait for a relaunched container to answer, then record what actually happened."""
        dep_id = dep["id"]
        timeout = int(
            (dep.get("satellite_parameters") or {}).get(
                "health_check_timeout", self.recovery_health_check_timeout
            )
        )

        async with ModelServerClient() as client:
            for _ in range(timeout):
                if await client.check_health_once(dep_id):
                    monitoring_enabled = self._read_monitoring_enabled(
                        dep.get("satellite_parameters")
                    )
                    await self.add_single_deployment(
                        dep_id,
                        dep.get("dynamic_attributes_secrets"),
                        monitoring_enabled=monitoring_enabled,
                    )
                    await platform.update_deployment(
                        dep_id, DeploymentUpdate(status=DeploymentStatus.ACTIVE)
                    )
                    logger.info(f"[ModelServerHandler] '{dep_id}' recovered")
                    return
                await asyncio.sleep(1)

        logs = await self._container_logs(docker, dep_id)
        await platform.update_deployment(
            dep_id,
            DeploymentUpdate(
                status=DeploymentStatus.NOT_RESPONDING,
                error_message={
                    "reason": "Relaunched container did not become healthy",
                    "error": (
                        f"Deployment '{dep_id}' was relaunched but did not answer in {timeout}s."
                        + (f"\n\nContainer logs:\n{logs[-3000:]}" if logs else "")
                    ),
                },
            ),
        )

    @staticmethod
    async def _container_logs(docker: DockerService, deployment_id: str) -> str:
        with suppress(Exception):
            container = await docker.client.containers.get(f"sat-{deployment_id}")
            logs = await container.log(stdout=True, stderr=True, follow=False, tail=100)
            return "".join(logs) if isinstance(logs, list) else str(logs)
        return ""

    async def sync_deployments(self) -> None:
        logger.info("[ModelServerHandler] sync_deployments...")
        async with (
            PlatformClient(str(config.PLATFORM_URL), config.SATELLITE_TOKEN) as platform_client,
            DockerService() as docker,
        ):
            deployments_db = await platform_client.list_deployments()
            # `not_responding` is in scope on purpose: it is where an earlier reconciliation
            # parks a deployment it could not revive, and where a recovery it started but did
            # not live to finish still sits. Leaving it out would make the first failure
            # permanent — the deployment stops being `active`, and nothing ever looks at it
            # again. `failed` and `pending` stay out: the first needs a real redeploy, the
            # second has a deploy task in flight that this must not race — which is why
            # recovery itself never writes `pending`.
            serving_deployments_db = [
                dep
                for dep in deployments_db
                if dep.get("status", "")
                in (DeploymentStatus.ACTIVE, DeploymentStatus.NOT_RESPONDING)
            ]

            logger.info(
                f"[serving_deployments_db] {[d.get('id', '') for d in serving_deployments_db]}"
            )

            recovering: list[dict[str, Any]] = []

            for dep in serving_deployments_db:
                dep_id = dep["id"]
                try:
                    labels = await docker.check_container_running(dep_id)
                except ContainerNotFoundError:
                    # No container at all: this Satellite holds nothing to restart. Creating
                    # one here would resurrect every deployment that ever failed on any
                    # Satellite, including ones abandoned months ago. Bringing a deployment
                    # back from nothing is a redeploy, and the Platform owns that decision.
                    await platform_client.update_deployment(
                        dep_id,
                        DeploymentUpdate(
                            status=DeploymentStatus.NOT_RESPONDING,
                            error_message=ErrorMessage(
                                reason="Not Found",
                                error=f"Container with deployment id '{dep_id}' not found",
                            ),
                        ),
                    )
                    continue
                except ContainerNotRunningError as e:
                    # The container exists but is stopped — the case this recovery is for.
                    if await self._relaunch(docker, platform_client, dep_id, str(e)):
                        recovering.append(dep)
                    continue

                if labels.get(LAUNCHER_PROTOCOL_LABEL) != LAUNCHER_PROTOCOL:
                    # A container launched under an older contract still carries what made
                    # the old world break — a presigned URL that expired long ago. It serves
                    # fine until its first restart, and that restart happens when nothing is
                    # watching. Replaced now instead, while the replacement can be watched.
                    if await self._relaunch(
                        docker,
                        platform_client,
                        dep_id,
                        "container was launched under an older Agent protocol",
                    ):
                        recovering.append(dep)
                    continue

                async with ModelServerClient() as client:
                    health_ok = await client.is_healthy(dep_id)

                if health_ok:
                    monitoring_enabled = self._read_monitoring_enabled(dep.get("monitoring_mode"))
                    await self.add_single_deployment(
                        dep_id,
                        dep.get("dynamic_attributes_secrets"),
                        monitoring_enabled=monitoring_enabled,
                        metadata=DeploymentMetadata.from_platform(dep),
                    )
                    await platform_client.update_deployment(
                        dep_id,
                        DeploymentUpdate(
                            monitoring_url=monitoring_url_for_deployment(
                                dep_id,
                                dep.get("monitoring_mode"),
                                monitoring_capability_present=config.MONITORING_ENABLED,
                            )
                        ),
                    )
                    # It answers, so whatever demoted it earlier is over.
                    if dep.get("status", "") != DeploymentStatus.ACTIVE:
                        await platform_client.update_deployment(
                            dep_id, DeploymentUpdate(status=DeploymentStatus.ACTIVE)
                        )
                elif (
                    dep.get("status", "") == DeploymentStatus.NOT_RESPONDING
                    and (dep.get("error_message") or {}).get("reason") == RECOVERING_REASON
                ):
                    # A recovery some earlier Agent began and did not live to see through:
                    # the container it relaunched runs, but is still booting. Wait for it
                    # the way that Agent would have — writing it off after one failed check
                    # would leave a container that answers minutes later serving nothing
                    # until the next restart.
                    recovering.append(dep)
                else:
                    logs = ""
                    with suppress(Exception):
                        container = await docker.client.containers.get(f"sat-{dep_id}")
                        logs_list = await container.log(
                            stdout=True, stderr=True, follow=False, tail=100
                        )
                        logs = "".join(logs_list) if isinstance(logs_list, list) else str(logs_list)
                    await platform_client.update_deployment(
                        dep_id,
                        DeploymentUpdate(
                            status=DeploymentStatus.NOT_RESPONDING,
                            error_message=ErrorMessage(
                                reason="Health check failed",
                                error=(
                                    f"Health check failed for deployment '{dep_id}'."
                                    + (f"\n\nContainer logs:\n{str(logs)[-3000:]}" if logs else "")
                                ),
                            ),
                        ),
                    )

            # Relaunched containers download and build their environment before they answer,
            # which takes minutes. They are waited on together rather than one after another:
            # a Satellite with several stopped deployments would otherwise take the sum of
            # their start-up times to reconcile.
            if recovering:
                await asyncio.gather(
                    *(self._settle_recovered(docker, platform_client, dep) for dep in recovering)
                )

            # Staging directories abandoned by hard-killed containers are reclaimed here
            # because nothing else ever will — each unpack uses a path of its own and only
            # cleans that. The sweep's age threshold keeps it away from unpacks still in
            # flight, including the ones this reconciliation just started.
            await docker.cleanup_stale_staging()

            logger.info(f"Synced deployments: {list(self.deployments.keys())}")

        self._invalidate_openapi_cache()

    @staticmethod
    async def get_compute_missing_secrets(
        deployment: LocalDeployment, compute_dynamic_atr: dict[str, Any]
    ) -> dict[str, Any]:
        missing_secrets: dict[str, str] = {}
        deployment_secrets = deployment.dynamic_attributes_secrets or {}

        secrets_to_fetch: list[tuple[str, str]] = []
        for attr_name, secret_id in deployment_secrets.items():
            if attr_name in compute_dynamic_atr:
                continue
            secrets_to_fetch.append((attr_name, secret_id))

        if not secrets_to_fetch:
            return compute_dynamic_atr

        try:
            async with PlatformClient(
                str(config.PLATFORM_URL), config.SATELLITE_TOKEN
            ) as platform_client:
                for attr_name, secret_id in secrets_to_fetch:
                    try:
                        secret_data = await platform_client.get_orbit_secret(UUID(secret_id))
                    except Exception as e:
                        logger.warning(
                            f"Failed to fetch secret '{attr_name}' (id={secret_id}): {e}"
                        )
                        secret_data = None

                    if secret_data:
                        secret = Secret.model_validate(secret_data)
                        missing_secrets[attr_name] = secret.value
        except Exception as error:
            logger.error("Failed to fetch secrets for compute: %s", error)

        return compute_dynamic_atr | missing_secrets

    async def model_compute(
        self, deployment_id: str, body: dict[str, Any]
    ) -> tuple[dict[str, Any], str | None]:
        deployment = await self.get_deployment(deployment_id)
        if not deployment:
            raise DeploymentNotHostedError()

        safe_inputs: dict[str, Any] | None = None
        should_instrument = deployment.monitoring_enabled and self._instrumentation is not None

        if should_instrument:
            safe_inputs = _extract_safe_inputs(body, deployment)

        body["dynamic_attributes"] = await self.get_compute_missing_secrets(
            deployment, body.get("dynamic_attributes") or {}
        )

        if should_instrument:
            assert self._instrumentation is not None

            async def _forward(*, extra_headers: dict[str, str] | None = None) -> dict:
                try:
                    async with ModelServerClient() as client:
                        return await client.compute(
                            deployment_id, body, extra_headers=extra_headers
                        )
                except ModelServerError:
                    raise
                except Exception as e:
                    raise RuntimeError(f"Model server request failed: {str(e)}") from e

            result, event_id = await self._instrumentation.instrumented_compute(
                deployment_id=deployment_id,
                safe_inputs=safe_inputs,
                forward_fn=_forward,
            )
            return result, event_id

        try:
            async with ModelServerClient() as client:
                result = await client.compute(deployment_id, body)
        except ModelServerError:
            raise
        except Exception as e:
            raise RuntimeError(f"Model server request failed: {str(e)}") from e
        return result, None

    async def get_deployment_schemas(self, deployment_id: str) -> dict[str, Any] | None:
        logger.info(f"[get_deployment_schemas] Starting for deployment_id='{deployment_id}'...")

        local_dep = await self.get_deployment(deployment_id)
        if local_dep is None or local_dep.openapi_schema is None:
            return None
        schema = local_dep.openapi_schema

        if local_dep.dynamic_attributes_secrets:
            dyna_props = (
                schema.get("components", {})
                .get("schemas", {})
                .get("DynamicAttributesModel", {})
                .get("properties", None)
            )
            if dyna_props:
                props_to_remove = [
                    prop for prop in dyna_props if prop in local_dep.dynamic_attributes_secrets
                ]
                for prop in props_to_remove:
                    dyna_props.pop(prop)

        return schema

    def register_openapi_cache_invalidation_callback(self, callback: Callable) -> None:
        self._openapi_cache_invalidation_callbacks.append(callback)

    def _invalidate_openapi_cache(self) -> None:
        for callback in self._openapi_cache_invalidation_callbacks:
            with suppress(Exception):
                callback()


def _extract_safe_inputs(body: dict, deployment: LocalDeployment) -> dict[str, Any] | None:
    """Capture the model input payload for monitoring, excluding secret-backed attributes.

    The model input payload (``body["inputs"]``) is required for data quality and feature
    drift, so it is recorded verbatim. Dynamic attributes are recorded too, but keys backed
    by secrets are dropped so secret values never reach local telemetry.
    """
    safe: dict[str, Any] = {}

    model_inputs = body.get("inputs")
    if model_inputs is not None:
        safe["inputs"] = model_inputs

    dynamic_attrs = body.get("dynamic_attributes")
    if dynamic_attrs is not None:
        secret_keys = set(deployment.dynamic_attributes_secrets or {})
        safe["dynamic_attributes"] = {
            k: v for k, v in dynamic_attrs.items() if k not in secret_keys
        }

    return safe or None
