"""Deployments and their monitoring, reached through the SDK.

The monitoring calls are the point: the Satellite's address comes out of the
deployment record itself, and the sections are read from the Satellite directly —
the Platform never sits in the data path.
"""

from unittest.mock import AsyncMock, Mock

import pytest

from luml_api._exceptions import LumlAPIError
from luml_api.resources.deployments import (
    AsyncDeploymentResource,
    DeploymentResource,
)

ORG = "0199c337-09f2-7af1-af5e-83fd7a5b51a0"
ORBIT = "0199c337-09f3-753e-9def-b27745e69be6"
DEPLOYMENT_ID = "01a033db-bb07-728a-9b5a-628c4cc6df94"
SATELLITE_ID = "0199c9cd-3e36-72c0-b823-040eb8195067"
SATELLITE_URL = "http://satellite.example"


def _record(**overrides) -> dict:
    record = {
        "id": DEPLOYMENT_ID,
        "orbit_id": ORBIT,
        "satellite_id": SATELLITE_ID,
        "satellite_name": "satellite",
        "name": "insurance regression",
        "artifact_id": "01a01502-ccff-720d-924b-7bbb13859f22",
        "artifact_name": "insurance_regression_v2",
        "collection_id": "0199c8cf-f4be-79ae-9251-b63108fd9009",
        "monitoring_url": f"/deployments/{DEPLOYMENT_ID}/monitoring",
        "status": "active",
        "monitoring_mode": "full",
        "created_at": "2026-08-24T13:00:00Z",
    }
    record.update(overrides)
    return record


def test_deployment_get_by_name_goes_through_the_listing(
    mock_sync_client: Mock,
) -> None:
    mock_sync_client.get.return_value = [_record()]

    deployment = DeploymentResource(mock_sync_client).get("insurance regression")

    mock_sync_client.get.assert_called_once_with(
        f"/v1/organizations/{ORG}/orbits/{ORBIT}/deployments"
    )
    assert deployment is not None
    assert deployment.monitoring_mode == "full"


def test_deployment_get_by_id_addresses_it_directly(mock_sync_client: Mock) -> None:
    mock_sync_client.get.return_value = _record()

    deployment = DeploymentResource(mock_sync_client).get(DEPLOYMENT_ID)

    mock_sync_client.get.assert_called_once_with(
        f"/v1/organizations/{ORG}/orbits/{ORBIT}/deployments/{DEPLOYMENT_ID}"
    )
    assert deployment is not None
    assert deployment.satellite_id == SATELLITE_ID
    assert deployment.monitoring_url == f"/deployments/{DEPLOYMENT_ID}/monitoring"


def test_monitoring_resolves_the_satellite_from_the_deployment(
    mock_sync_client: Mock,
) -> None:
    mock_sync_client.get.side_effect = [
        _record(),  # the deployment
        {"id": SATELLITE_ID, "base_url": SATELLITE_URL},  # its satellite
        {"state": "ok", "cards": []},  # the section, served by the satellite
    ]

    monitoring = DeploymentResource(mock_sync_client).monitoring(DEPLOYMENT_ID)
    overview = monitoring.overview(window="7d", severity="critical")

    section_call = mock_sync_client.get.call_args_list[-1]
    assert section_call.args[0] == (
        f"{SATELLITE_URL}/deployments/{DEPLOYMENT_ID}/monitoring/overview"
    )
    assert section_call.kwargs["params"]["window"] == "7d"
    assert section_call.kwargs["params"]["severity"] == "critical"
    assert overview["state"] == "ok"


def test_monitoring_sections_share_one_address_scheme(mock_sync_client: Mock) -> None:
    mock_sync_client.get.side_effect = [
        _record(),
        {"base_url": SATELLITE_URL},
    ]
    monitoring = DeploymentResource(mock_sync_client).monitoring(DEPLOYMENT_ID)

    mock_sync_client.get.reset_mock()
    mock_sync_client.get.side_effect = None
    mock_sync_client.get.return_value = {}
    monitoring.runtime()
    monitoring.data_quality(feature="age")
    monitoring.output_drift(severity="critical")
    monitoring.alerts(severity="warning")
    monitoring.traces(limit=5, offset=10, sort="latency", order="asc")
    monitoring.trace("evt-1")
    monitoring.worker()

    urls = [call.args[0] for call in mock_sync_client.get.call_args_list]
    base = f"{SATELLITE_URL}/deployments/{DEPLOYMENT_ID}/monitoring"
    assert urls == [
        f"{base}/runtime",
        f"{base}/data-quality",
        f"{base}/output-drift",
        f"{base}/alerts",
        f"{base}/traces",
        f"{base}/traces/evt-1",
        f"{base}/worker",
    ]
    dq_params = mock_sync_client.get.call_args_list[1].kwargs["params"]
    assert dq_params["feature"] == "age"
    traces_params = mock_sync_client.get.call_args_list[4].kwargs["params"]
    assert traces_params["limit"] == "5"
    assert traces_params["sort"] == "latency"
    assert traces_params["order"] == "asc"


def test_monitoring_refuses_a_satellite_without_an_address(
    mock_sync_client: Mock,
) -> None:
    """A Satellite the browser cannot reach cannot serve an SDK either — say so."""
    mock_sync_client.get.side_effect = [_record(), {"base_url": None}]

    with pytest.raises(LumlAPIError, match="no reachable base URL"):
        DeploymentResource(mock_sync_client).monitoring(DEPLOYMENT_ID)


def test_traces_rejects_a_sort_the_log_does_not_offer(mock_sync_client: Mock) -> None:
    mock_sync_client.get.side_effect = [_record(), {"base_url": SATELLITE_URL}]
    monitoring = DeploymentResource(mock_sync_client).monitoring(DEPLOYMENT_ID)

    with pytest.raises(LumlAPIError, match="sort must be one of"):
        monitoring.traces(sort="color")
    with pytest.raises(LumlAPIError, match="order must be one of"):
        monitoring.traces(order="sideways")


def test_monitoring_rejects_a_window_the_dashboard_does_not_offer(
    mock_sync_client: Mock,
) -> None:
    mock_sync_client.get.side_effect = [_record(), {"base_url": SATELLITE_URL}]
    monitoring = DeploymentResource(mock_sync_client).monitoring(DEPLOYMENT_ID)

    with pytest.raises(LumlAPIError, match="window"):
        monitoring.overview(window="90d")


@pytest.mark.asyncio
async def test_async_monitoring_mirrors_the_sync_flow(
    mock_async_client: AsyncMock,
) -> None:
    mock_async_client.get = AsyncMock(
        side_effect=[
            _record(),
            {"base_url": SATELLITE_URL},
            {"state": "ok"},
        ]
    )

    monitoring = await AsyncDeploymentResource(mock_async_client).monitoring(
        DEPLOYMENT_ID
    )
    overview = await monitoring.overview()

    section_call = mock_async_client.get.call_args_list[-1]
    assert section_call.args[0] == (
        f"{SATELLITE_URL}/deployments/{DEPLOYMENT_ID}/monitoring/overview"
    )
    assert overview["state"] == "ok"


def test_deployment_list_is_empty_when_the_platform_says_nothing(
    mock_sync_client: Mock,
) -> None:
    mock_sync_client.get.return_value = None

    assert DeploymentResource(mock_sync_client).list() == []


def test_deployment_get_by_name_returns_none_when_absent(
    mock_sync_client: Mock,
) -> None:
    mock_sync_client.get.return_value = [_record()]

    assert DeploymentResource(mock_sync_client).get("no such deployment") is None


def test_monitoring_accepts_a_deployment_name_not_just_an_id(
    mock_sync_client: Mock,
) -> None:
    """The dashboard is opened by name; the SDK should not demand more."""
    mock_sync_client.get.side_effect = [
        [_record()],  # the listing the name is resolved through
        {"base_url": SATELLITE_URL},
    ]

    monitoring = DeploymentResource(mock_sync_client).monitoring("insurance regression")

    assert monitoring.deployment_id == DEPLOYMENT_ID


def test_monitoring_normalizes_a_trailing_slash_in_the_satellite_url(
    mock_sync_client: Mock,
) -> None:
    """The stand stores base URLs like "http://localhost/" — no double slashes."""
    mock_sync_client.get.side_effect = [
        _record(),
        {"base_url": SATELLITE_URL + "/"},
        {},
    ]

    DeploymentResource(mock_sync_client).monitoring(DEPLOYMENT_ID).worker()

    url = mock_sync_client.get.call_args_list[-1].args[0]
    assert url == f"{SATELLITE_URL}/deployments/{DEPLOYMENT_ID}/monitoring/worker"


def test_reference_profile_scopes_to_one_feature_when_asked(
    mock_sync_client: Mock,
) -> None:
    mock_sync_client.get.side_effect = [
        _record(),
        {"base_url": SATELLITE_URL},
    ]
    monitoring = DeploymentResource(mock_sync_client).monitoring(DEPLOYMENT_ID)

    mock_sync_client.get.reset_mock()
    mock_sync_client.get.side_effect = None
    mock_sync_client.get.return_value = {}
    monitoring.reference_profile(feature="age")
    monitoring.reference_profile()

    scoped = mock_sync_client.get.call_args_list[0].kwargs["params"]
    unscoped = mock_sync_client.get.call_args_list[1].kwargs["params"]
    assert scoped["feature"] == "age"
    # absent, not null: the whole document is addressed by leaving the feature out
    assert "feature" not in unscoped


@pytest.mark.parametrize("section", ["runtime", "alerts", "traces"])
def test_every_windowed_section_rejects_a_window_the_dashboard_lacks(
    mock_sync_client: Mock, section: str
) -> None:
    mock_sync_client.get.side_effect = [_record(), {"base_url": SATELLITE_URL}]
    monitoring = DeploymentResource(mock_sync_client).monitoring(DEPLOYMENT_ID)

    with pytest.raises(LumlAPIError, match="window"):
        getattr(monitoring, section)(window="1h")


@pytest.mark.asyncio
async def test_async_monitoring_refuses_a_satellite_without_an_address(
    mock_async_client: AsyncMock,
) -> None:
    mock_async_client.get = AsyncMock(side_effect=[_record(), {"base_url": ""}])

    with pytest.raises(LumlAPIError, match="no reachable base URL"):
        await AsyncDeploymentResource(mock_async_client).monitoring(DEPLOYMENT_ID)


@pytest.mark.asyncio
async def test_async_get_by_name_goes_through_the_listing(
    mock_async_client: AsyncMock,
) -> None:
    mock_async_client.get = AsyncMock(return_value=[_record()])

    deployment = await AsyncDeploymentResource(mock_async_client).get(
        "insurance regression"
    )

    assert deployment is not None
    assert deployment.id == DEPLOYMENT_ID
