import logging
from uuid import UUID

from agent.handlers.handler_instances import ms_handler
from agent.schemas import (
    DeploymentStatus,
    DeploymentUpdate,
    SatelliteQueueTask,
    SatelliteTaskStatus,
)
from agent.schemas.deployments import ErrorMessage
from agent.tasks.base import Task

logger = logging.getLogger(__name__)


class UndeployTask(Task):
    async def run(self, task: SatelliteQueueTask) -> None:
        await self.platform.update_task_status(task.id, SatelliteTaskStatus.RUNNING)

        payload = task.payload or {}
        try:
            deployment_id = UUID(str(payload["deployment_id"]))
        except (KeyError, TypeError, ValueError):
            await self.platform.update_task_status(
                task.id,
                SatelliteTaskStatus.FAILED,
                ErrorMessage(reason="Invalid task payload.", error="Missing deployment_id."),
            )
            return
        deployment_key = str(deployment_id)

        try:
            container_removed, model_id = await self.docker.remove_model_container(
                deployment_id=deployment_id
            )
        except Exception as error:
            error_message = ErrorMessage(
                reason="Failed to remove container.",
                error=str(error),
            )
            await self.platform.update_task_status(
                task.id, SatelliteTaskStatus.FAILED, error_message
            )
            await self.platform.update_deployment(
                deployment_key,
                DeploymentUpdate(
                    error_message=error_message, status=DeploymentStatus.DELETION_FAILED
                ),
            )
            return

        try:
            await self.platform.delete_deployment(deployment_id)
        except Exception as error:
            error_message = ErrorMessage(reason="Failed to delete deployment.", error=str(error))
            await self.platform.update_task_status(
                task.id, SatelliteTaskStatus.FAILED, error_message
            )
            await self.platform.update_deployment(
                deployment_key,
                DeploymentUpdate(
                    error_message=error_message, status=DeploymentStatus.DELETION_FAILED
                ),
            )
            return

        await ms_handler.remove_deployment(deployment_id)

        # Best effort: the deployment is already gone, so a failed cleanup must not fail
        # the task — it only leaves the cache entry for the next undeploy or sweep.
        # The records are asked before the containers: replacement is delete-then-create,
        # and mid-gap a live deployment of the same artifact briefly holds no container —
        # a reference count alone would call its warm cache unused and delete it.
        if model_id:
            try:
                records = await self.platform.list_deployments()
                if any(str(dep.get("artifact_id", "")) == model_id for dep in records):
                    logger.info(
                        f"[UndeployTask] Model '{model_id}' is still referenced by a "
                        f"deployment; keeping its cache."
                    )
                else:
                    await self.docker.cleanup_model_cache(model_id)
            except Exception as error:
                logger.error(
                    f"[UndeployTask] Failed to clean model '{model_id}' cache.\n{str(error)}"
                )

        await self.platform.update_task_status(
            task.id,
            SatelliteTaskStatus.DONE,
            {"container_removed": container_removed},
        )
