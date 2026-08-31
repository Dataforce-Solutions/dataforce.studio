from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from agent.handlers.handler_instances import ms_handler
from agent.handlers.tasks import TaskHandler
from agent.schemas import (
    Deployment,
    DeploymentStatus,
    SatelliteQueueTask,
    SatelliteTaskStatus,
    SatelliteTaskType,
)
from agent.settings import config

DEPLOYMENT_ID = "0199c337-09f7-751e-add2-d952f0d6cf4e"
ARTIFACT_ID = "0199c337-09fa-7ff6-b1e7-fc89a65f8622"


def _task() -> SatelliteQueueTask:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return SatelliteQueueTask(
        id="task-1",
        satellite_id="sat-1",
        orbit_id="orbit-1",
        type=SatelliteTaskType.DEPLOY,
        payload={"deployment_id": DEPLOYMENT_ID},
        status=SatelliteTaskStatus.PENDING,
        scheduled_at=now,
        created_at=now,
    )


def _deployment(
    monitoring_mode: str, status: str = "pending", inference_url: str | None = None
) -> Deployment:
    return Deployment(
        id=DEPLOYMENT_ID,
        orbit_id="orbit-1",
        satellite_id="sat-1",
        satellite_name="sat",
        name="dep",
        artifact_id=ARTIFACT_ID,
        artifact_name="model",
        collection_id="col-1",
        status=status,
        inference_url=inference_url,
        monitoring_mode=monitoring_mode,
        created_at="2026-01-01T00:00:00Z",
    )


class TestDeployTask:
    @pytest.mark.parametrize(
        ("monitoring_capability_present", "monitoring_mode", "expected_url"),
        [
            (True, "full", f"/deployments/{DEPLOYMENT_ID}/monitoring"),
            (True, "off", None),
            (False, "full", None),
        ],
    )
    async def test_deploy_reports_monitoring_url_when_available(
        self,
        monkeypatch: pytest.MonkeyPatch,
        monitoring_capability_present: bool,
        monitoring_mode: str,
        expected_url: str | None,
    ) -> None:
        monkeypatch.setattr(config, "MONITORING_ENABLED", monitoring_capability_present)
        platform = AsyncMock()
        platform.get_deployment.return_value = _deployment(monitoring_mode)
        platform.get_artifact_download_url.return_value = "https://artifacts.example/model.luml"
        docker = AsyncMock()
        docker.run_model_container.return_value = AsyncMock()
        client = AsyncMock()
        client.check_health_once.return_value = True
        client_context = AsyncMock()
        client_context.__aenter__.return_value = client
        schemas = {"input": {"type": "object"}}
        task_handler = TaskHandler(platform=platform, docker=docker)._handlers[
            SatelliteTaskType.DEPLOY
        ]

        with (
            patch("agent.tasks.deploy.ModelServerClient", return_value=client_context),
            patch("agent.tasks.deploy.ms_handler.add_deployment", new=AsyncMock()),
            patch(
                "agent.tasks.deploy.ms_handler.get_deployment_schemas",
                new=AsyncMock(return_value=schemas),
            ),
        ):
            await task_handler.run(_task())

        update = platform.update_deployment.await_args.args[1]
        assert update.model_dump(exclude_unset=True) == {
            "status": DeploymentStatus.ACTIVE,
            "inference_url": f"/deployments/{DEPLOYMENT_ID}",
            "monitoring_url": expected_url,
            "schemas": schemas,
            # cleared explicitly: the Platform honours only the fields actually sent
            "error_message": None,
        }

    async def test_the_header_shows_the_record_the_platform_answered_with(
        self, monkeypatch: pytest.MonkeyPatch, mock_model_server: object
    ) -> None:
        """A freshly deployed model used to sit at `pending` in the dashboard header.

        The deployment is registered locally from the record fetched while it was still
        pending, and only then flipped to active on the Platform; the header repeated
        the stale word until the next reconciliation. The PATCH answers with the record
        as it now is, and that is what the header shows.
        """
        monkeypatch.setattr(config, "MONITORING_ENABLED", True)
        inference_url = f"/deployments/{DEPLOYMENT_ID}"
        platform = AsyncMock()
        platform.get_deployment.return_value = _deployment("full")  # pending, no URL yet
        platform.get_artifact_download_url.return_value = "https://artifacts.example/model.luml"
        platform.update_deployment.return_value = _deployment(
            "full", status="active", inference_url=inference_url
        )
        docker = AsyncMock()
        docker.run_model_container.return_value = AsyncMock()
        client = AsyncMock()
        client.check_health_once.return_value = True
        client_context = AsyncMock()
        client_context.__aenter__.return_value = client
        task_handler = TaskHandler(platform=platform, docker=docker)._handlers[
            SatelliteTaskType.DEPLOY
        ]

        try:
            with patch("agent.tasks.deploy.ModelServerClient", return_value=client_context):
                await task_handler.run(_task())

            local = ms_handler.deployments[DEPLOYMENT_ID]
            assert local.metadata.status == "active"
            assert local.metadata.inference_url == inference_url
            assert local.metadata.name == "dep"
        finally:
            ms_handler.deployments.pop(DEPLOYMENT_ID, None)

    async def test_a_docker_error_during_the_wait_does_not_strand_the_deployment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The container check is an early exit for a container that died — not a verdict.

        A daemon error there used to escape the wait: the task was marked failed while the
        record stayed `pending` with its container running, and reconciliation skips
        pending records. The model's own health answer decides, within the deadline.
        """
        from aiodocker.exceptions import DockerError

        monkeypatch.setattr(config, "MONITORING_ENABLED", False)
        platform = AsyncMock()
        platform.get_deployment.return_value = _deployment("off")
        platform.get_artifact_download_url.return_value = "https://artifacts.example/model.luml"
        platform.update_deployment.return_value = _deployment(
            "off", status="active", inference_url=f"/deployments/{DEPLOYMENT_ID}"
        )
        docker = AsyncMock()
        docker.run_model_container.return_value = AsyncMock()
        docker.check_container_running = AsyncMock(
            side_effect=DockerError(500, {"message": "daemon is busy"})
        )
        client = AsyncMock()
        client.check_health_once.side_effect = [False, True]  # answers on the second look
        client_context = AsyncMock()
        client_context.__aenter__.return_value = client
        task_handler = TaskHandler(platform=platform, docker=docker)._handlers[
            SatelliteTaskType.DEPLOY
        ]

        with (
            patch("agent.tasks.deploy.ModelServerClient", return_value=client_context),
            patch("agent.tasks.deploy.ms_handler.add_deployment", new=AsyncMock()),
            patch(
                "agent.tasks.deploy.ms_handler.get_deployment_schemas",
                new=AsyncMock(return_value={}),
            ),
            patch("agent.tasks.deploy.asyncio.sleep", new=AsyncMock()),
        ):
            await task_handler.run(_task())

        statuses = [c.args[1].status for c in platform.update_deployment.await_args_list]
        assert statuses == [DeploymentStatus.ACTIVE]
        task_status = platform.update_task_status.await_args_list[-1].args[1]
        assert task_status == SatelliteTaskStatus.DONE
        docker.remove_model_container.assert_not_awaited()

    async def test_a_failed_finalization_is_what_the_header_shows(
        self, monkeypatch: pytest.MonkeyPatch, mock_model_server: object
    ) -> None:
        """The task-status write fails after the deployment was already marked active.

        The fallback marks the deployment failed on the Platform; the header must not
        keep saying `active` from the write that succeeded a moment earlier.
        """
        monkeypatch.setattr(config, "MONITORING_ENABLED", False)
        inference_url = f"/deployments/{DEPLOYMENT_ID}"
        platform = AsyncMock()
        platform.get_deployment.return_value = _deployment("off")
        platform.get_artifact_download_url.return_value = "https://artifacts.example/model.luml"
        platform.update_deployment.side_effect = [
            _deployment("off", status="active", inference_url=inference_url),
            _deployment("off", status="failed", inference_url=inference_url),
        ]
        platform.update_task_status.side_effect = [
            None,  # RUNNING
            RuntimeError("platform hiccup on DONE"),
            None,  # FAILED
        ]
        docker = AsyncMock()
        docker.run_model_container.return_value = AsyncMock()
        client = AsyncMock()
        client.check_health_once.return_value = True
        client_context = AsyncMock()
        client_context.__aenter__.return_value = client
        task_handler = TaskHandler(platform=platform, docker=docker)._handlers[
            SatelliteTaskType.DEPLOY
        ]

        try:
            with patch("agent.tasks.deploy.ModelServerClient", return_value=client_context):
                await task_handler.run(_task())

            statuses = [c.args[1].status for c in platform.update_deployment.await_args_list]
            assert statuses == [DeploymentStatus.ACTIVE, DeploymentStatus.FAILED]
            assert ms_handler.deployments[DEPLOYMENT_ID].metadata.status == "failed"
        finally:
            ms_handler.deployments.pop(DEPLOYMENT_ID, None)
