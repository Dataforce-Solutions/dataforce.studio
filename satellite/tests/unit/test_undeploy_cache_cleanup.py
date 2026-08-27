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


class TestUndeployCacheCleanup:
    async def test_undeploy_cleans_the_removed_containers_cache_entry(self) -> None:
        task = _undeploy_task()

        await task.run(_task())

        task.docker.cleanup_model_cache.assert_awaited_once_with(MODEL_ID)

    async def test_a_container_without_a_model_label_triggers_no_cleanup(self) -> None:
        """Legacy containers predate the label; guessing a cache key would delete blind."""
        task = _undeploy_task(model_id=None)

        await task.run(_task())

        task.docker.cleanup_model_cache.assert_not_awaited()

    async def test_a_model_still_referenced_by_a_record_keeps_its_cache(self) -> None:
        """Records outrank container reference counts.

        Replacement is delete-then-create: mid-gap a live deployment of the same
        artifact holds no container, and a reference count alone would call its warm
        cache unused.
        """
        task = _undeploy_task()
        task.platform.list_deployments = AsyncMock(return_value=[{"artifact_id": MODEL_ID}])

        await task.run(_task())

        task.docker.cleanup_model_cache.assert_not_awaited()

    async def test_a_model_no_record_references_is_cleaned(self) -> None:
        task = _undeploy_task()
        task.platform.list_deployments = AsyncMock(return_value=[{"artifact_id": "other-artifact"}])

        await task.run(_task())

        task.docker.cleanup_model_cache.assert_awaited_once_with(MODEL_ID)

    async def test_a_failed_cleanup_does_not_fail_the_undeploy(self) -> None:
        """The deployment is already gone; a lingering cache entry is the lesser evil."""
        task = _undeploy_task()
        task.docker.cleanup_model_cache = AsyncMock(side_effect=RuntimeError("docker is down"))

        await task.run(_task())

        final_status = task.platform.update_task_status.await_args.args[1]
        assert final_status == SatelliteTaskStatus.DONE

    async def test_a_model_another_deployment_still_uses_is_not_deleted(self) -> None:
        """The cache volume is per artifact, shared by every deployment of that artifact."""
        with patch("agent.clients.docker_client.aiodocker.Docker"):
            service = DockerService()
            other_container = AsyncMock()
            other_container.show = AsyncMock(
                return_value={"Config": {"Labels": {"df.model_id": MODEL_ID}}}
            )
            service.client.containers.list = AsyncMock(return_value=[other_container])
            service.client.volumes.get = AsyncMock()

            await service.cleanup_model_cache(MODEL_ID)

            service.client.volumes.get.assert_not_awaited()

    async def test_the_last_deployments_model_loses_its_cache_volume(self) -> None:
        from agent.clients.docker_client import model_cache_volume

        with patch("agent.clients.docker_client.aiodocker.Docker"):
            service = DockerService()
            service.client.containers.list = AsyncMock(return_value=[])
            volume = AsyncMock()
            service.client.volumes.get = AsyncMock(return_value=volume)

            await service.cleanup_model_cache(MODEL_ID)

            service.client.volumes.get.assert_awaited_once_with(model_cache_volume(MODEL_ID))
            volume.delete.assert_awaited_once()

    async def test_a_model_that_was_never_cached_here_is_not_an_error(self) -> None:
        """A deployment can be undeployed before its container ever downloaded anything."""
        from aiodocker.exceptions import DockerError

        with patch("agent.clients.docker_client.aiodocker.Docker"):
            service = DockerService()
            service.client.containers.list = AsyncMock(return_value=[])
            service.client.volumes.get = AsyncMock(
                side_effect=DockerError(404, {"message": "no such volume"})
            )

            await service.cleanup_model_cache(MODEL_ID)  # must simply return, not raise
