import json

import httpx
import pytest
import respx

from agent.handlers.model_server_handler import ModelServerHandler
from agent.schemas.deployments import Deployment, LocalDeployment
from agent.settings import config

# The mock must follow PLATFORM_URL from the environment, not a pinned literal.
PLATFORM_URL = str(config.PLATFORM_URL).rstrip("/")


def _make_deployment(
    monitoring_mode: str = "off",
    deployment_id: str = "dep-1",
) -> Deployment:
    return Deployment(
        id=deployment_id,
        orbit_id="orbit-1",
        satellite_id="sat-1",
        satellite_name="test-sat",
        name="test-dep",
        artifact_id="art-1",
        artifact_name="model-a",
        collection_id="col-1",
        status="active",
        monitoring_mode=monitoring_mode,
        created_at="2026-01-01T00:00:00Z",
    )


class TestMonitoringFlag:
    # --- read monitoring enabled ---
    def test_true_when_full(self) -> None:
        assert ModelServerHandler._read_monitoring_enabled("full") is True

    def test_false_when_off(self) -> None:
        assert ModelServerHandler._read_monitoring_enabled("off") is False

    def test_false_when_none(self) -> None:
        assert ModelServerHandler._read_monitoring_enabled(None) is False

    def test_true_case_insensitive(self) -> None:
        assert ModelServerHandler._read_monitoring_enabled("FULL") is True

    def test_false_when_unknown(self) -> None:
        assert ModelServerHandler._read_monitoring_enabled("garbage") is False

    # --- local deployment monitoring default ---
    def test_defaults_to_false(self) -> None:
        ld = LocalDeployment(deployment_id="dep-1")
        assert ld.monitoring_enabled is False

    def test_can_be_set_true(self) -> None:
        ld = LocalDeployment(deployment_id="dep-1", monitoring_enabled=True)
        assert ld.monitoring_enabled is True

    # --- add deployment carries flag ---
    @respx.mock
    async def test_monitoring_enabled_propagated(self, mock_model_server: None) -> None:
        handler = ModelServerHandler()
        dep = _make_deployment(monitoring_mode="full")
        await handler.add_deployment(dep)

        local = handler.deployments[dep.id]
        assert local.monitoring_enabled is True

    @respx.mock
    async def test_monitoring_disabled_by_default(self, mock_model_server: None) -> None:
        handler = ModelServerHandler()
        dep = _make_deployment()
        await handler.add_deployment(dep)

        local = handler.deployments[dep.id]
        assert local.monitoring_enabled is False

    # --- sync deployments carries flag ---
    @pytest.mark.parametrize(
        ("monitoring_capability_present", "expected_monitoring_url"),
        [
            (True, "/deployments/dep-sync-1/monitoring"),
            (False, None),
        ],
    )
    @respx.mock
    async def test_sync_reads_monitoring_mode(
        self,
        monkeypatch: pytest.MonkeyPatch,
        monitoring_capability_present: bool,
        expected_monitoring_url: str | None,
    ) -> None:
        monkeypatch.setattr(config, "MONITORING_ENABLED", monitoring_capability_present)
        handler = ModelServerHandler()
        deployment_record = {
            "id": "dep-sync-1",
            "orbit_id": "orbit-1",
            "satellite_id": "sat-1",
            "satellite_name": "test-sat",
            "name": "synced deployment",
            "artifact_id": "art-1",
            "artifact_name": "model-a",
            "collection_id": "col-1",
            "inference_url": "/deployments/dep-sync-1",
            "status": "active",
            "monitoring_mode": "full",
            "dynamic_attributes_secrets": {},
            "created_at": "2026-01-01T00:00:00Z",
        }

        respx.get(f"{PLATFORM_URL}/satellites/v1/deployments").mock(
            return_value=httpx.Response(200, json=[deployment_record])
        )
        update_route = respx.patch(f"{PLATFORM_URL}/satellites/v1/deployments/dep-sync-1").mock(
            return_value=httpx.Response(
                200,
                json=deployment_record | {"monitoring_url": expected_monitoring_url},
            )
        )

        # Mock model server endpoints for this specific deployment
        respx.get(url__regex=r"http://sat-dep-sync-1:\d+/healthz").mock(
            return_value=httpx.Response(200, json={"status": "healthy"})
        )
        respx.get(url__regex=r"http://sat-dep-sync-1:\d+/manifest").mock(
            return_value=httpx.Response(200, json={"name": "test", "version": "1"})
        )
        respx.get(url__regex=r"http://sat-dep-sync-1:\d+/openapi\.json").mock(
            return_value=httpx.Response(200, json={"openapi": "3.0.0"})
        )

        # We need to mock docker. sync_deployments creates its own clients,
        # so we patch the docker check at the handler level.
        from unittest.mock import AsyncMock, patch

        from agent.handlers.container_launcher import LAUNCHER_PROTOCOL, LAUNCHER_PROTOCOL_LABEL

        mock_docker = AsyncMock()
        mock_docker.check_container_running = AsyncMock(
            return_value={LAUNCHER_PROTOCOL_LABEL: LAUNCHER_PROTOCOL}
        )
        mock_docker.__aenter__ = AsyncMock(return_value=mock_docker)
        mock_docker.__aexit__ = AsyncMock(return_value=False)

        with patch("agent.handlers.model_server_handler.DockerService", return_value=mock_docker):
            await handler.sync_deployments()

        assert "dep-sync-1" in handler.deployments
        local = handler.deployments["dep-sync-1"]
        assert local.monitoring_enabled is True
        # the dashboard header reads its identity from here, not from telemetry
        assert local.metadata.name == "synced deployment"
        assert local.metadata.status == "active"
        assert local.metadata.model_name == "model-a"
        assert local.metadata.satellite == "test-sat"
        assert local.metadata.inference_url == "/deployments/dep-sync-1"
        assert json.loads(update_route.calls[0].request.content) == {
            "monitoring_url": expected_monitoring_url
        }

    @respx.mock
    async def test_sync_absent_mode_means_off(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(config, "MONITORING_ENABLED", True)
        handler = ModelServerHandler()
        deployment_record = {
            "id": "dep-sync-2",
            "status": "active",
            "dynamic_attributes_secrets": {},
        }
        update_response = {
            "id": "dep-sync-2",
            "orbit_id": "orbit-1",
            "satellite_id": "sat-1",
            "satellite_name": "test-sat",
            "name": "synced deployment",
            "artifact_id": "art-1",
            "artifact_name": "model-a",
            "collection_id": "col-1",
            "status": "active",
            "dynamic_attributes_secrets": {},
            "created_at": "2026-01-01T00:00:00Z",
        }

        respx.get(f"{PLATFORM_URL}/satellites/v1/deployments").mock(
            return_value=httpx.Response(200, json=[deployment_record])
        )
        update_route = respx.patch(f"{PLATFORM_URL}/satellites/v1/deployments/dep-sync-2").mock(
            return_value=httpx.Response(
                200,
                json=update_response | {"monitoring_url": None},
            )
        )

        respx.get(url__regex=r"http://sat-dep-sync-2:\d+/healthz").mock(
            return_value=httpx.Response(200, json={"status": "healthy"})
        )
        respx.get(url__regex=r"http://sat-dep-sync-2:\d+/manifest").mock(
            return_value=httpx.Response(200, json={"name": "test", "version": "1"})
        )
        respx.get(url__regex=r"http://sat-dep-sync-2:\d+/openapi\.json").mock(
            return_value=httpx.Response(200, json={"openapi": "3.0.0"})
        )

        from unittest.mock import AsyncMock, patch

        from agent.handlers.container_launcher import LAUNCHER_PROTOCOL, LAUNCHER_PROTOCOL_LABEL

        mock_docker = AsyncMock()
        mock_docker.check_container_running = AsyncMock(
            return_value={LAUNCHER_PROTOCOL_LABEL: LAUNCHER_PROTOCOL}
        )
        mock_docker.__aenter__ = AsyncMock(return_value=mock_docker)
        mock_docker.__aexit__ = AsyncMock(return_value=False)

        with patch("agent.handlers.model_server_handler.DockerService", return_value=mock_docker):
            await handler.sync_deployments()

        assert "dep-sync-2" in handler.deployments
        local = handler.deployments["dep-sync-2"]
        assert local.monitoring_enabled is False
        # a record without those fields simply leaves the header empty
        assert local.metadata.name is None
        assert json.loads(update_route.calls[0].request.content) == {"monitoring_url": None}
