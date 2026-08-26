"""Undeploy reclaims the cache entry its deployment used — nothing else ever will.

Extracted models live on a shared volume precisely so they outlive any one container, which
means no container's death frees them. The undeploy task is the only moment the Satellite
knows a model may have lost its last user, so it is where the cache is cleaned — and only
when no other deployment still uses the same artifact.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from agent.clients.docker_client import DockerService
from agent.schemas import SatelliteQueueTask, SatelliteTaskStatus, SatelliteTaskType
from agent.tasks.undeploy import UndeployTask

MODEL_ID = "01a014fd-0000-7021-b0f5-fe92f2fdaf9b"


def _task() -> SatelliteQueueTask:
    now = datetime.now(UTC)
    return SatelliteQueueTask(
        id=str(uuid.uuid4()),
        satellite_id=str(uuid.uuid4()),
        orbit_id=str(uuid.uuid4()),
        type=SatelliteTaskType.UNDEPLOY,
        payload={"deployment_id": str(uuid.uuid4())},
        status=SatelliteTaskStatus.PENDING,
        scheduled_at=now,
        created_at=now,
    )


def _undeploy_task(*, model_id: str | None = MODEL_ID) -> UndeployTask:
    docker = AsyncMock()
    docker.remove_model_container = AsyncMock(return_value=(True, model_id))
    return UndeployTask(platform=AsyncMock(), docker=docker)


async def test_undeploy_cleans_the_removed_containers_cache_entry() -> None:
    task = _undeploy_task()

    await task.run(_task())

    task.docker.cleanup_model_cache.assert_awaited_once_with(MODEL_ID)


async def test_a_container_without_a_model_label_triggers_no_cleanup() -> None:
    """Legacy containers predate the label; guessing a cache key would delete blind."""
    task = _undeploy_task(model_id=None)

    await task.run(_task())

    task.docker.cleanup_model_cache.assert_not_awaited()


async def test_a_failed_cleanup_does_not_fail_the_undeploy() -> None:
    """The deployment is already gone; a lingering cache entry is the lesser evil."""
    task = _undeploy_task()
    task.docker.cleanup_model_cache = AsyncMock(side_effect=RuntimeError("docker is down"))

    await task.run(_task())

    final_status = task.platform.update_task_status.await_args.args[1]
    assert final_status == SatelliteTaskStatus.DONE


async def test_a_model_another_deployment_still_uses_is_not_deleted() -> None:
    """The cache key is the artifact id, shared by every deployment of that artifact."""
    with patch("agent.clients.docker_client.aiodocker.Docker"):
        service = DockerService()
        other_container = AsyncMock()
        other_container.show = AsyncMock(
            return_value={"Config": {"Labels": {"df.model_id": MODEL_ID}}}
        )
        service.client.containers.list = AsyncMock(return_value=[other_container])
        service.client.containers.create = AsyncMock()

        await service.cleanup_model_cache(MODEL_ID)

        service.client.containers.create.assert_not_awaited()


async def test_the_last_deployments_model_is_deleted() -> None:
    with patch("agent.clients.docker_client.aiodocker.Docker"):
        service = DockerService()
        service.client.containers.list = AsyncMock(return_value=[])
        service.client.containers.create = AsyncMock()
        service.client.images.get = AsyncMock()

        await service.cleanup_model_cache(MODEL_ID)

        config_arg = service.client.containers.create.await_args.kwargs["config"]
        assert f"/app/models/{MODEL_ID}" in config_arg["Cmd"]
