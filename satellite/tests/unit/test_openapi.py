import json
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from agent.agent_api import OpenAPISchemaBuilder, create_agent_app
from agent.schemas.monitoring import MonitoringIntrospection
from agent.settings import config

GOOD_KEY = "dfs_good"
# Shared with the SDK contract test, which reads the same file from satellite/tests.
OPENAPI_SNAPSHOT = Path(__file__).parents[1] / "snapshots" / "static_openapi.json"


async def _authorize(api_key: str) -> bool:
    return api_key == GOOD_KEY


async def _introspect(token: str) -> MonitoringIntrospection:
    return MonitoringIntrospection(active=False)


@pytest.fixture()
def app() -> FastAPI:
    return create_agent_app(_authorize, _introspect)


@pytest.fixture()
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as test_client:
        yield test_client


class TestOpenAPI:
    def test_machine_operations_have_facets_security_and_descriptions(self, app: FastAPI) -> None:
        schema = app.openapi()
        expected_facets = {
            ("post", "/satellites/deployments/inference-access"): "satellite",
            ("get", "/healthz"): "satellite",
            ("get", "/deployments"): "deployment",
            ("post", "/deployments/{deployment_id}/compute"): "deployment",
            ("get", "/deployments/{deployment_id}/monitoring/header"): "deployment:monitoring",
            ("get", "/deployments/{deployment_id}/monitoring/overview"): "deployment:monitoring",
            ("get", "/deployments/{deployment_id}/monitoring/runtime"): "deployment:monitoring",
            (
                "get",
                "/deployments/{deployment_id}/monitoring/data-quality",
            ): "deployment:monitoring",
            (
                "get",
                "/deployments/{deployment_id}/monitoring/feature-drift",
            ): "deployment:monitoring",
            (
                "get",
                "/deployments/{deployment_id}/monitoring/output-drift",
            ): "deployment:monitoring",
            (
                "get",
                "/deployments/{deployment_id}/monitoring/reference-profile",
            ): "deployment:monitoring",
            ("get", "/deployments/{deployment_id}/monitoring/alerts"): "deployment:monitoring",
            ("get", "/deployments/{deployment_id}/monitoring/traces"): "deployment:monitoring",
            (
                "get",
                "/deployments/{deployment_id}/monitoring/traces/{event_id}",
            ): "deployment:monitoring",
            ("get", "/deployments/{deployment_id}/monitoring/worker"): "deployment:monitoring",
        }

        paths = schema["paths"]
        assert isinstance(paths, dict)
        machine_operations = {
            (method, path): operation
            for path, path_item in paths.items()
            if not path.startswith("/monitoring/") and isinstance(path_item, dict)
            for method, operation in path_item.items()
            if method in {"get", "post", "put", "patch", "delete"} and isinstance(operation, dict)
        }

        assert set(machine_operations) == set(expected_facets)

        for (method, path), facet in expected_facets.items():
            operation = machine_operations[(method, path)]
            assert operation["tags"] == [facet]
            assert isinstance(operation.get("summary"), str)
            assert operation["summary"]
            assert isinstance(operation.get("description"), str)
            assert operation["description"]
            expected_security: list[dict[str, list[str]]] = (
                [] if path == "/satellites/deployments/inference-access" else [{"HTTPBearer": []}]
            )
            assert operation["security"] == expected_security

        components = schema["components"]
        assert isinstance(components, dict)
        assert components["securitySchemes"] == {"HTTPBearer": {"type": "http", "scheme": "bearer"}}

    def test_full_static_openapi_matches_contract_snapshot(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(config, "MONITORING_ENABLED", True)
        app = create_agent_app(_authorize, _introspect)

        schema = OpenAPISchemaBuilder.generate_full_static_schema(app)
        snapshot = json.loads(OPENAPI_SNAPSHOT.read_text())

        assert schema == snapshot

    def test_dashboard_operations_are_untagged_and_described(self, app: FastAPI) -> None:
        schema = app.openapi()
        paths = schema["paths"]
        assert isinstance(paths, dict)

        dashboard_operations = [
            operation
            for path, path_item in paths.items()
            if path.startswith("/monitoring/") and isinstance(path_item, dict)
            for operation in path_item.values()
            if isinstance(operation, dict)
        ]

        assert dashboard_operations
        for operation in dashboard_operations:
            assert "tags" not in operation
            assert isinstance(operation.get("summary"), str)
            assert operation["summary"]
            assert isinstance(operation.get("description"), str)
            assert operation["description"]

    @pytest.mark.parametrize("path", ["/openapi.json", "/docs", "/redoc"])
    async def test_docs_require_a_bearer_key(
        self,
        client: httpx.AsyncClient,
        path: str,
    ) -> None:
        response = await client.get(path)

        assert response.status_code in (401, 403)

    @pytest.mark.parametrize("path", ["/openapi.json", "/docs", "/redoc"])
    async def test_docs_are_served_with_a_valid_bearer_key(
        self,
        client: httpx.AsyncClient,
        path: str,
    ) -> None:
        response = await client.get(path, headers={"Authorization": f"Bearer {GOOD_KEY}"})

        assert response.status_code == 200

    @pytest.mark.parametrize("path", ["/openapi.json", "/docs", "/redoc"])
    async def test_docs_reject_an_invalid_bearer_key(
        self,
        client: httpx.AsyncClient,
        path: str,
    ) -> None:
        response = await client.get(path, headers={"Authorization": "Bearer dfs_wrong"})

        assert response.status_code == 401

    async def test_health_requires_bearer_but_inference_access_does_not(
        self,
        client: httpx.AsyncClient,
    ) -> None:
        health_without_key = await client.get("/healthz")
        health_with_key = await client.get(
            "/healthz", headers={"Authorization": f"Bearer {GOOD_KEY}"}
        )
        inference_access = await client.post(
            "/satellites/deployments/inference-access", json={"api_key": GOOD_KEY}
        )

        assert health_without_key.status_code in (401, 403)
        assert health_with_key.status_code == 200
        assert inference_access.status_code == 200
        assert inference_access.json() == {"authorized": True}
