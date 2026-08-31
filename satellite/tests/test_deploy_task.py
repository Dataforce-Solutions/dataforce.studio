from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

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


def _deployment(monitoring_mode: str) -> Deployment:
    return Deployment(
        id=DEPLOYMENT_ID,
        orbit_id="orbit-1",
        satellite_id="sat-1",
        satellite_name="sat",
        name="dep",
        artifact_id=ARTIFACT_ID,
        artifact_name="model",
        collection_id="col-1",
        status="pending",
        monitoring_mode=monitoring_mode,
        created_at="2026-01-01T00:00:00Z",
    )


@pytest.mark.parametrize(
    ("monitoring_capability_present", "monitoring_mode", "expected_url"),
    [
        (True, "full", f"/deployments/{DEPLOYMENT_ID}/monitoring"),
        (True, "off", None),
        (False, "full", None),
    ],
)
async def test_deploy_reports_monitoring_url_when_available(
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
    task_handler = TaskHandler(platform=platform, docker=docker)._handlers[SatelliteTaskType.DEPLOY]

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
