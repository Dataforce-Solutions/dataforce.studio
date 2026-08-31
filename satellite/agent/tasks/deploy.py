import asyncio
import logging
from uuid import UUID

from aiodocker.containers import DockerContainer

from agent._exceptions import ContainerNotFoundError, ContainerNotRunningError
from agent.clients import ModelServerClient
from agent.handlers.container_launcher import launch_model_container
from agent.handlers.handler_instances import ms_handler
from agent.schemas import (
    Deployment,
    DeploymentStatus,
    DeploymentUpdate,
    SatelliteQueueTask,
    SatelliteTaskStatus,
    monitoring_url_for_deployment,
)
from agent.schemas.deployments import ErrorMessage
from agent.settings import config
from agent.tasks.base import Task

logger = logging.getLogger(__name__)


class DeployTask(Task):
    default_health_check_timeout = 1800

    async def _handle_healthcheck_timeout(
        self, container: DockerContainer, task_id: str, dep_id: str
    ) -> None:
        try:
            logs_response = await container.log(stdout=True, stderr=True, follow=False, tail=80)
            logs = (
                "".join(logs_response)
                if isinstance(logs_response, list)
                else str(logs_response or "")
            )
        except Exception:
            logs = ""
        error_message = ErrorMessage(reason="healthcheck timeout", error=str(logs)[-1000:])
        await self.platform.update_task_status(task_id, SatelliteTaskStatus.FAILED, error_message)
        await self.platform.update_deployment(
            dep_id, DeploymentUpdate(status=DeploymentStatus.FAILED, error_message=error_message)
        )

    async def _get_deployment(self, dep_id: str, task_id: str) -> Deployment:
        try:
            deployment = await self.platform.get_deployment(UUID(dep_id))
            if not deployment:
                raise ValueError("deployment not found")
            return deployment
        except Exception as e:
            error_message = ErrorMessage(reason="failed to get deployment details", error=str(e))
            await self.platform.update_task_status(
                task_id, SatelliteTaskStatus.FAILED, error_message
            )
            await self.platform.update_deployment(
                dep_id,
                DeploymentUpdate(status=DeploymentStatus.FAILED, error_message=error_message),
            )
            raise

    async def _handle_container_creation_error(
        self, task_id: str, dep_id: str, error_str: str
    ) -> None:
        if "No such image" in error_str or "not found" in error_str.lower():
            error_message = ErrorMessage(
                reason="Docker image not found",
                error=f"Image '{config.MODEL_IMAGE}' not found. "
                f"Please ensure the image is built or pulled on the satellite.",
            )
        else:
            error_message = ErrorMessage(reason="Failed to create container", error=error_str)

        logger.error(f"Failed to run container for deployment {dep_id}: {error_str}")
        await self.platform.update_task_status(task_id, SatelliteTaskStatus.FAILED, error_message)
        await self.platform.update_deployment(
            dep_id,
            DeploymentUpdate(status=DeploymentStatus.FAILED, error_message=error_message),
        )

    async def _handle_deploying_error(
        self, container: DockerContainer, task_id: str, dep_id: str, error_str: str
    ) -> None:
        try:
            logs_response = await container.log(stdout=True, stderr=True, follow=False, tail=100)
            logs = (
                "".join(logs_response)
                if isinstance(logs_response, list)
                else str(logs_response or "")
            )
        except Exception:
            logs = ""

        error_message = ErrorMessage(
            reason="Container stopped or not found",
            error=f"{error_str}\n\nLogs:\n{str(logs)[-1000:]}",
        )
        logger.error(f"[deploy] Container {dep_id} check failed: {error_message}")
        await self.platform.update_task_status(task_id, SatelliteTaskStatus.FAILED, error_message)
        await self.platform.update_deployment(
            dep_id,
            DeploymentUpdate(status=DeploymentStatus.FAILED, error_message=error_message),
        )

    async def run(self, task: SatelliteQueueTask) -> None:
        await self.platform.update_task_status(task.id, SatelliteTaskStatus.RUNNING)

        dep_id = (task.payload or {}).get("deployment_id")
        if not isinstance(dep_id, str):
            await self.platform.update_task_status(
                task.id,
                SatelliteTaskStatus.FAILED,
                ErrorMessage(
                    reason="Failed to deploy model", error="Missing deployment_id in task."
                ),
            )
            return
        try:
            dep = await self._get_deployment(dep_id, task.id)
        except Exception:
            return

        satellite_params = dep.satellite_parameters or {}
        health_check_timeout = satellite_params.get(
            "health_check_timeout", self.default_health_check_timeout
        )

        try:
            container = await launch_model_container(self.platform, self.docker, dep)
        except Exception as e:
            await self._handle_container_creation_error(task.id, dep_id, str(e))
            return

        inference_url = f"/deployments/{dep_id}"

        health_ok = False
        loop = asyncio.get_running_loop()
        deadline = loop.time() + int(health_check_timeout)
        next_container_check = loop.time()
        async with ModelServerClient() as client:
            while loop.time() < deadline:
                if loop.time() >= next_container_check:
                    try:
                        await self.docker.check_container_running(dep_id)
                    except (ContainerNotFoundError, ContainerNotRunningError) as e:
                        await self._handle_deploying_error(container, task.id, dep_id, str(e))
                        return
                    except Exception as error:  # noqa: BLE001 — Docker's silence is not a verdict
                        # The container check only shortens the wait for a container that
                        # died; whether the model is up is the health endpoint's call.
                        # Failing here would leave the record pending with its container
                        # running, which nothing reconciles.
                        logger.warning(
                            f"[deploy] could not inspect the container of '{dep_id}': "
                            f"{error}; still waiting for it to answer"
                        )
                    next_container_check = loop.time() + 5

                if await client.check_health_once(dep_id):
                    health_ok = True
                    break

                await asyncio.sleep(1)

        if not health_ok:
            await self._handle_healthcheck_timeout(container, task.id, dep_id)
            return

        try:
            await ms_handler.add_deployment(dep)
            schemas = await ms_handler.get_deployment_schemas(dep_id)

            activated = await self.platform.update_deployment(
                dep_id,
                DeploymentUpdate(
                    inference_url=inference_url,
                    monitoring_url=monitoring_url_for_deployment(
                        dep_id,
                        dep.monitoring_mode,
                        monitoring_capability_present=config.MONITORING_ENABLED,
                    ),
                    schemas=schemas,
                    status=DeploymentStatus.ACTIVE,
                    error_message=None,
                ),
            )
            # registered from the record as it was while pending; the header shows this one
            ms_handler.note_platform_record(dep_id, activated)
            await self.platform.update_task_status(
                task.id,
                SatelliteTaskStatus.DONE,
                {"inference_url": inference_url},
            )
        except Exception as e:
            logger.error(f"Failed to finalize deployment {dep_id}: {e}", exc_info=True)
            error_message = ErrorMessage(reason="failed to finalize deployment", error=str(e))
            await self.platform.update_task_status(
                task.id, SatelliteTaskStatus.FAILED, error_message
            )
            await self.platform.update_deployment(
                dep_id,
                DeploymentUpdate(status=DeploymentStatus.FAILED, error_message=error_message),
            )
