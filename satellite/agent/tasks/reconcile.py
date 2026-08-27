import logging

from agent.handlers.handler_instances import ms_handler
from agent.schemas import (
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


class ReconcileTask(Task):
    async def run(self, task: SatelliteQueueTask) -> None:
        await self.platform.update_task_status(task.id, SatelliteTaskStatus.RUNNING)

        payload = task.payload or {}
        deployment_id = payload.get("deployment_id")
        if not deployment_id:
            await self.platform.update_task_status(
                task.id,
                SatelliteTaskStatus.FAILED,
                {"reason": "missing deployment_id"},
            )
            return

        try:
            deployment = await self.platform.get_deployment(deployment_id)
        except Exception as error:
            await self.platform.update_task_status(
                task.id,
                SatelliteTaskStatus.FAILED,
                ErrorMessage(reason="Failed to fetch deployment.", error=str(error)),
            )
            return

        if deployment.status != DeploymentStatus.ACTIVE:
            # Nothing running to reconcile; the eventual deploy/sync applies the mode.
            await self.platform.update_task_status(
                task.id,
                SatelliteTaskStatus.DONE,
                {"reconciled": False, "reason": f"status={deployment.status}"},
            )
            return

        try:
            await ms_handler.add_deployment(deployment)
            await self.platform.update_deployment(
                deployment_id,
                DeploymentUpdate(
                    monitoring_url=monitoring_url_for_deployment(
                        deployment_id,
                        deployment.monitoring_mode,
                        monitoring_capability_present=config.MONITORING_ENABLED,
                    )
                ),
            )
        except Exception as error:
            await self.platform.update_task_status(
                task.id,
                SatelliteTaskStatus.FAILED,
                ErrorMessage(reason="Failed to reconcile deployment.", error=str(error)),
            )
            return

        await self.platform.update_task_status(
            task.id,
            SatelliteTaskStatus.DONE,
            {"reconciled": True, "monitoring_enabled": deployment.monitoring_mode == "full"},
        )
