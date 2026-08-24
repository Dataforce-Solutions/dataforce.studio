"""The machine surface: monitoring as a facet of the deployment tree.

A bearer key is valid for a whole orbit and carries no deployment, so the request names
its deployment in the path — and the surface shares one credential story with inference,
while the browser world under /monitoring keeps its cookie sessions. These tests pin the
door, not the data behind it: the sections themselves are covered by the query-service
tests.
"""

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from tests.support import FIXED_NOW

from agent.agent_api import create_agent_app
from agent.handlers.handler_instances import ms_handler
from agent.monitoring import MonitoringQueryService
from agent.monitoring.health import worker_health
from agent.monitoring.query_store import EventStatus, InferenceEvent, InMemoryMonitoringStore
from agent.schemas import DeploymentMetadata, LocalDeployment
from agent.schemas.monitoring import MonitoringIntrospection

DEPLOYMENT_ID = uuid.uuid4()
OTHER_DEPLOYMENT_ID = uuid.uuid4()
GOOD_KEY = "dfs_good"


async def _authorize(api_key: str) -> bool:
    if api_key == "boom":
        raise RuntimeError("platform down")
    return api_key == GOOD_KEY


async def _introspect(token: str) -> MonitoringIntrospection:
    return MonitoringIntrospection(active=False)


@pytest.fixture()
def app():  # noqa: ANN201
    application = create_agent_app(_authorize, _introspect)
    # The wiring under test is the routes and the door; the data behind them comes from
    # a deterministic in-memory store instead of whatever GreptimeDB the host runs.
    store = InMemoryMonitoringStore()
    store.add_event(
        InferenceEvent(
            event_id="evt-1",
            deployment_id=DEPLOYMENT_ID,
            ts=datetime.fromtimestamp(FIXED_NOW - 60, tz=UTC),
            status=EventStatus.SUCCESS,
            status_code=200,
            latency_ms=12.0,
        )
    )
    application.state.monitoring_query = MonitoringQueryService(store, clock=lambda: FIXED_NOW)

    ms_handler.deployments[str(DEPLOYMENT_ID)] = LocalDeployment(
        deployment_id=str(DEPLOYMENT_ID),
        monitoring_enabled=True,
        metadata=DeploymentMetadata(name="insurance", status="active"),
    )
    yield application
    ms_handler.deployments.pop(str(DEPLOYMENT_ID), None)


def _client(app) -> httpx.AsyncClient:  # noqa: ANN001
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    )


def _url(section: str = "overview", deployment: uuid.UUID = DEPLOYMENT_ID) -> str:
    return f"/deployments/{deployment}/monitoring/{section}"


def _bearer(key: str = GOOD_KEY) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


async def test_a_key_reads_any_section_of_a_hosted_deployment(app) -> None:  # noqa: ANN001
    async with _client(app) as client:
        overview = await client.get(_url("overview"), headers=_bearer())
        runtime = await client.get(_url("runtime"), headers=_bearer())
        output_drift = await client.get(_url("output-drift"), headers=_bearer())

    assert overview.status_code == 200
    assert overview.json()["state"] == "ok"
    assert runtime.status_code == 200
    assert runtime.json()["request_count"] == 1
    # no materialized output window in the seeded store: empty, but served
    assert output_drift.status_code == 200
    assert output_drift.json()["state"] == "empty"


async def test_without_a_credential_the_door_stays_shut(app) -> None:  # noqa: ANN001
    async with _client(app) as client:
        resp = await client.get(_url())

    assert resp.status_code == 403


async def test_a_rejected_key_is_unauthenticated(app) -> None:  # noqa: ANN001
    async with _client(app) as client:
        resp = await client.get(_url(), headers=_bearer("dfs_wrong"))

    assert resp.status_code == 401


async def test_an_unverifiable_key_fails_closed(app) -> None:  # noqa: ANN001
    """Platform unreachable and nothing cached: refuse, never trust."""
    async with _client(app) as client:
        resp = await client.get(_url(), headers=_bearer("boom"))

    assert resp.status_code == 502


async def test_a_deployment_this_satellite_does_not_host_is_not_found(app) -> None:  # noqa: ANN001
    async with _client(app) as client:
        resp = await client.get(_url(deployment=OTHER_DEPLOYMENT_ID), headers=_bearer())

    assert resp.status_code == 404


async def test_a_dashboard_cookie_does_not_open_the_machine_surface(app) -> None:  # noqa: ANN001
    """One credential per surface: sessions stay in the browser world."""
    client = _client(app)
    client.cookies.set("monitoring_session", "some-session")
    async with client:
        resp = await client.get(_url())

    assert resp.status_code == 403


async def test_the_machine_surface_is_read_only(app) -> None:  # noqa: ANN001
    """Acknowledging alerts stays on the session surface: machines watch, a person decides."""
    async with _client(app) as client:
        resp = await client.post(
            _url("alerts/acknowledge"), headers=_bearer(), json={"metric": "runtime:error_rate"}
        )

    assert resp.status_code in (404, 405)


async def test_the_listing_says_what_is_monitored_here(app, mock_model_server) -> None:  # noqa: ANN001
    worker_health.window_processed(
        str(DEPLOYMENT_ID),
        datetime.fromtimestamp(FIXED_NOW - 300, tz=UTC),
        datetime.fromtimestamp(FIXED_NOW, tz=UTC),
    )
    try:
        async with _client(app) as client:
            resp = await client.get("/deployments", headers=_bearer())
    finally:
        worker_health._deployments.pop(str(DEPLOYMENT_ID), None)

    assert resp.status_code == 200
    rows = {row["deployment_id"]: row for row in resp.json()}
    row = rows[str(DEPLOYMENT_ID)]
    assert row["name"] == "insurance"
    assert row["status"] == "active"
    assert row["monitoring_mode"] == "full"
    assert row["last_monitored_at"] is not None
