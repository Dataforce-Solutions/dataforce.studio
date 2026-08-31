import json
from typing import Any

import httpx
import pytest
import respx
from fastapi import FastAPI

from agent.agent_api import create_agent_app
from agent.agent_manager import SatelliteManager
from agent.clients import PlatformClient
from agent.monitoring import (
    DataQualityMetric,
    MetricRegistry,
    MultivariateDriftMetric,
    default_registry,
)
from agent.schemas.monitoring import MonitoringIntrospection
from agent.settings import config


async def _authorize(api_key: str) -> bool:
    return True


async def _introspect(token: str) -> MonitoringIntrospection:
    return MonitoringIntrospection(active=False)


def _operations(openapi: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    methods = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
    return [
        (path, operation)
        for path, path_item in openapi["paths"].items()
        if isinstance(path_item, dict)
        for method, operation in path_item.items()
        if method in methods and isinstance(operation, dict)
    ]


class TestCapabilities:
    def test_capabilities_include_versioned_deploy_and_monitoring_declarations(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(config, "MONITORING_ENABLED", True)

        capabilities = SatelliteManager.get_capabilities(default_registry())

        assert capabilities == {
            "deploy": {
                "version": 1,
                "api_versions": [1],
                "facets": ["satellite", "deployment"],
                "supported_variants": ["pyfunc", "pipeline"],
                "supported_tags_combinations": None,
                "extra_fields_form_spec": [],
            },
            "monitoring": {
                "version": 1,
                "api_versions": [1],
                "facets": ["deployment:monitoring"],
                "features": [
                    "runtime",
                    "traces",
                    "alerts",
                    "data_quality",
                    "feature_drift",
                    "output_drift",
                    "multivariate_drift",
                ],
            },
        }

    def test_monitoring_features_follow_registered_metrics(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(config, "MONITORING_ENABLED", True)
        registry = MetricRegistry([DataQualityMetric(), MultivariateDriftMetric()])

        capabilities = SatelliteManager.get_capabilities(registry)

        assert capabilities["monitoring"]["features"] == [
            "runtime",
            "traces",
            "alerts",
            "data_quality",
            "multivariate_drift",
        ]

    def test_monitoring_disabled_advertises_deploy_only(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(config, "MONITORING_ENABLED", False)

        capabilities = SatelliteManager.get_capabilities(default_registry())

        assert set(capabilities) == {"deploy"}

    @pytest.mark.parametrize(
        ("monitoring_enabled", "expected_facets"),
        [
            (True, {"satellite", "deployment", "deployment:monitoring"}),
            (False, {"satellite", "deployment"}),
        ],
    )
    async def test_pair_pushes_static_openapi_for_advertised_capabilities(
        self,
        monkeypatch: pytest.MonkeyPatch,
        respx_mock: respx.MockRouter,
        monitoring_enabled: bool,
        expected_facets: set[str],
    ) -> None:
        monkeypatch.setattr(config, "MONITORING_ENABLED", monitoring_enabled)
        monkeypatch.setattr(config, "BASE_URL", "https://satellite.example/")
        app: FastAPI = create_agent_app(_authorize, _introspect)
        app.openapi_schema = {
            "openapi": "3.1.0",
            "paths": {"/runtime-only": {}},
            "components": {"schemas": {"DeploymentRuntimeOnly": {}}},
        }
        pair_route = respx_mock.post("https://platform.example/satellites/v1/pair").mock(
            return_value=httpx.Response(200, json={})
        )

        async with PlatformClient("https://platform.example", "token") as platform:
            manager = SatelliteManager(platform, app, default_registry())
            await manager.pair()

        payload = json.loads(pair_route.calls[0].request.content)
        openapi = payload["openapi"]
        operations = _operations(openapi)

        assert operations
        assert {operation["tags"][0] for _, operation in operations} == expected_facets
        assert all(len(operation["tags"]) == 1 for _, operation in operations)
        assert all(not path.startswith("/monitoring/") for path, _ in operations)
        assert "/runtime-only" not in openapi["paths"]
        assert "DeploymentRuntimeOnly" not in openapi["components"]["schemas"]
        assert payload["base_url"] == "https://satellite.example"
        assert ("monitoring" in payload["capabilities"]) is monitoring_enabled
        monitoring_paths = [
            path for path, operation in operations if operation["tags"] == ["deployment:monitoring"]
        ]
        assert bool(monitoring_paths) is monitoring_enabled
