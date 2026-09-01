from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from agent.handlers.tasks import TaskHandler
from agent.schemas import SatelliteQueueTask, SatelliteTaskStatus, SatelliteTaskType
from agent.schemas.deployments import Deployment
from agent.settings import config
from agent.tasks import ReconcileTask


def _task(deployment_id: str | None = "dep-1") -> SatelliteQueueTask:
    return SatelliteQueueTask(
        id="task-1",
        satellite_id="sat-1",
        orbit_id="orbit-1",
        type=SatelliteTaskType.RECONCILE,
        payload={"deployment_id": deployment_id} if deployment_id else {},
        status=SatelliteTaskStatus.PENDING,
        scheduled_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )


def _deployment(monitoring_mode: str = "full", status: str = "active") -> Deployment:
    return Deployment(
        id="dep-1",
        orbit_id="orbit-1",
        satellite_id="sat-1",
        satellite_name="sat",
        name="dep",
        artifact_id="art-1",
        artifact_name="model",
        collection_id="col-1",
        status=status,
        monitoring_mode=monitoring_mode,
        created_at="2026-01-01T00:00:00Z",
    )


class TestReconcileTask:
    async def test_reconcile_active_reapplies_monitoring(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(config, "MONITORING_ENABLED", True)
        platform = AsyncMock()
        platform.get_deployment.return_value = _deployment(monitoring_mode="full")
        task_handler = ReconcileTask(platform=platform, docker=AsyncMock())

        with patch("agent.tasks.reconcile.ms_handler.add_deployment", new=AsyncMock()) as add_dep:
            await task_handler.run(_task())

        add_dep.assert_awaited_once()
        # last status update marks the task done with reconciled=True
        final_status = platform.update_task_status.await_args_list[-1]
        assert final_status.args[1] == SatelliteTaskStatus.DONE
        assert final_status.args[2]["reconciled"] is True
        assert final_status.args[2]["monitoring_enabled"] is True
        update = platform.update_deployment.await_args.args[1]
        assert update.model_dump(exclude_unset=True) == {
            "monitoring_url": "/deployments/dep-1/monitoring"
        }

    async def test_reconcile_clears_and_restores_monitoring_url(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(config, "MONITORING_ENABLED", True)
        platform = AsyncMock()
        platform.get_deployment.side_effect = [
            _deployment(monitoring_mode="off"),
            _deployment(monitoring_mode="full"),
        ]
        task_handler = ReconcileTask(platform=platform, docker=AsyncMock())

        with patch("agent.tasks.reconcile.ms_handler.add_deployment", new=AsyncMock()):
            await task_handler.run(_task())
            await task_handler.run(_task())

        updates = [call.args[1] for call in platform.update_deployment.await_args_list]
        assert [update.model_dump(exclude_unset=True) for update in updates] == [
            {"monitoring_url": None},
            {"monitoring_url": "/deployments/dep-1/monitoring"},
        ]

    async def test_reconcile_inactive_skips_add_deployment(self) -> None:
        platform = AsyncMock()
        platform.get_deployment.return_value = _deployment(status="pending")
        task_handler = ReconcileTask(platform=platform, docker=AsyncMock())

        with patch("agent.tasks.reconcile.ms_handler.add_deployment", new=AsyncMock()) as add_dep:
            await task_handler.run(_task())

        add_dep.assert_not_awaited()
        final_status = platform.update_task_status.await_args_list[-1]
        assert final_status.args[1] == SatelliteTaskStatus.DONE
        assert final_status.args[2]["reconciled"] is False

    async def test_reconcile_missing_deployment_id_fails(self) -> None:
        platform = AsyncMock()
        task_handler = ReconcileTask(platform=platform, docker=AsyncMock())

        await task_handler.run(_task(deployment_id=None))

        platform.get_deployment.assert_not_called()
        final_status = platform.update_task_status.await_args_list[-1]
        assert final_status.args[1] == SatelliteTaskStatus.FAILED

    def test_dispatch_registers_reconcile_handler(self) -> None:
        handler = TaskHandler(platform=AsyncMock(), docker=AsyncMock())
        assert isinstance(handler._handlers[SatelliteTaskType.RECONCILE], ReconcileTask)
