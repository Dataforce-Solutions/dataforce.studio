"""Startup reconciliation of model containers that are no longer running.

The artifact URL a container carries is presigned and expires in hours, while the container
lives for weeks. A stopped container can therefore never simply be started again — it would
try to download its model from a dead link. These tests pin the recovery: recreate it, with
a URL signed at that moment.
"""

import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from agent._exceptions import ContainerNotFoundError, ContainerNotRunningError
from agent.handlers.model_server_handler import ModelServerHandler
from agent.settings import config

PLATFORM_URL = str(config.PLATFORM_URL).rstrip("/")

DEPLOYMENT_ID = "01a014fd-1ebc-7021-b0f5-fe92f2fdaf9b"
ARTIFACT_ID = "01a014fd-0000-7021-b0f5-fe92f2fdaf9b"
FRESH_URL = "https://s3.example.com/artifacts/iris.luml?X-Amz-Signature=fresh"


def _platform_record() -> dict:
    return {
        "id": DEPLOYMENT_ID,
        "orbit_id": str(uuid.uuid4()),
        "satellite_id": str(uuid.uuid4()),
        "satellite_name": "test-sat",
        "name": "iris",
        "artifact_id": ARTIFACT_ID,
        "artifact_name": "iris_classification",
        "collection_id": str(uuid.uuid4()),
        "status": "active",
        "satellite_parameters": {"monitoring_enabled": True},
        "dynamic_attributes_secrets": {},
        "env_variables": {},
        "env_variables_secrets": {},
        "created_at": "2026-08-18T13:10:44Z",
    }


def _mock_platform(*, record: dict | None = None) -> None:
    record = record or _platform_record()
    respx.get(f"{PLATFORM_URL}/satellites/v1/deployments").mock(
        return_value=httpx.Response(200, json=[record])
    )
    respx.get(f"{PLATFORM_URL}/satellites/v1/deployments/{DEPLOYMENT_ID}").mock(
        return_value=httpx.Response(200, json=record)
    )
    respx.get(f"{PLATFORM_URL}/satellites/v1/artifacts/{ARTIFACT_ID}/download-url").mock(
        return_value=httpx.Response(200, json={"url": FRESH_URL})
    )


def _mock_model_server(*, healthy: bool = True) -> None:
    code = 200 if healthy else 503
    respx.get(url__regex=rf"http://sat-{DEPLOYMENT_ID}:\d+/healthz").mock(
        return_value=httpx.Response(code, json={"status": "healthy" if healthy else "down"})
    )
    respx.get(url__regex=rf"http://sat-{DEPLOYMENT_ID}:\d+/manifest").mock(
        return_value=httpx.Response(200, json={"name": "iris", "version": "1"})
    )
    respx.get(url__regex=rf"http://sat-{DEPLOYMENT_ID}:\d+/openapi\.json").mock(
        return_value=httpx.Response(200, json={"openapi": "3.0.0"})
    )
    respx.get(url__regex=rf"http://sat-{DEPLOYMENT_ID}:\d+/reference_profile").mock(
        return_value=httpx.Response(404)
    )


def _stopped_docker() -> AsyncMock:
    docker = AsyncMock()
    docker.check_container_running = AsyncMock(
        side_effect=ContainerNotRunningError(DEPLOYMENT_ID, "exited")
    )
    docker.__aenter__ = AsyncMock(return_value=docker)
    docker.__aexit__ = AsyncMock(return_value=False)
    return docker


def _patched(docker: AsyncMock):  # noqa: ANN202 — test helper
    return patch("agent.handlers.model_server_handler.DockerService", return_value=docker)


@respx.mock
async def test_stopped_container_is_recreated_with_a_freshly_signed_url() -> None:
    handler = ModelServerHandler()
    _mock_platform()
    _mock_model_server()
    patch_route = respx.patch(
        f"{PLATFORM_URL}/satellites/v1/deployments/{DEPLOYMENT_ID}"
    ).mock(return_value=httpx.Response(200, json=_platform_record()))
    docker = _stopped_docker()

    with _patched(docker):
        await handler.sync_deployments()

    docker.run_model_container.assert_awaited_once()
    env = docker.run_model_container.await_args.kwargs["env"]
    # the whole point: the URL is minted now, not reused from the dead container
    assert env["MODEL_ARTIFACT_URL"] == FRESH_URL
    assert env["MODEL_NAME"] == "iris_classification"
    assert docker.run_model_container.await_args.kwargs["name"] == f"sat-{DEPLOYMENT_ID}"

    # once it answers, the deployment is serving again and known locally
    assert DEPLOYMENT_ID in handler.deployments
    assert handler.deployments[DEPLOYMENT_ID].monitoring_enabled is True
    # pending while it boots, active once it answers
    updates = [call.request.read() for call in patch_route.calls]
    assert b'"pending"' in updates[0]
    assert b'"active"' in updates[-1]


@respx.mock
async def test_a_container_that_cannot_be_recreated_is_reported_not_responding() -> None:
    handler = ModelServerHandler()
    _mock_platform()
    _mock_model_server()
    respx.get(f"{PLATFORM_URL}/satellites/v1/artifacts/{ARTIFACT_ID}/download-url").mock(
        return_value=httpx.Response(403, json={"detail": "artifact gone"})
    )
    patch_route = respx.patch(
        f"{PLATFORM_URL}/satellites/v1/deployments/{DEPLOYMENT_ID}"
    ).mock(return_value=httpx.Response(200, json=_platform_record()))
    docker = _stopped_docker()

    with _patched(docker):
        await handler.sync_deployments()

    docker.run_model_container.assert_not_awaited()
    assert DEPLOYMENT_ID not in handler.deployments
    assert b'"not_responding"' in patch_route.calls[-1].request.read()


@respx.mock
async def test_a_recreated_container_that_never_answers_is_reported_not_responding() -> None:
    handler = ModelServerHandler()
    handler.recovery_health_check_timeout = 1  # one attempt, not thirty minutes
    _mock_platform()
    _mock_model_server(healthy=False)
    patch_route = respx.patch(
        f"{PLATFORM_URL}/satellites/v1/deployments/{DEPLOYMENT_ID}"
    ).mock(return_value=httpx.Response(200, json=_platform_record()))
    docker = _stopped_docker()

    with _patched(docker):
        await handler.sync_deployments()

    docker.run_model_container.assert_awaited_once()
    assert DEPLOYMENT_ID not in handler.deployments
    assert b'"not_responding"' in patch_route.calls[-1].request.read()


@respx.mock
async def test_a_deployment_an_earlier_run_gave_up_on_is_still_recovered() -> None:
    """Otherwise the first failed reconciliation is permanent.

    Marking a deployment `not_responding` takes it out of `active`, so a reconciliation that
    only looked at `active` would never see it again — exactly the dead end this recovery
    exists to remove.
    """
    handler = ModelServerHandler()
    record = _platform_record() | {"status": "not_responding"}
    _mock_platform(record=record)
    _mock_model_server()
    patch_route = respx.patch(
        f"{PLATFORM_URL}/satellites/v1/deployments/{DEPLOYMENT_ID}"
    ).mock(return_value=httpx.Response(200, json=record))
    docker = _stopped_docker()

    with _patched(docker):
        await handler.sync_deployments()

    docker.run_model_container.assert_awaited_once()
    assert DEPLOYMENT_ID in handler.deployments
    assert b'"active"' in patch_route.calls[-1].request.read()


@respx.mock
async def test_a_recovered_container_that_still_runs_is_promoted_back_to_active() -> None:
    handler = ModelServerHandler()
    record = _platform_record() | {"status": "not_responding"}
    _mock_platform(record=record)
    _mock_model_server()
    patch_route = respx.patch(
        f"{PLATFORM_URL}/satellites/v1/deployments/{DEPLOYMENT_ID}"
    ).mock(return_value=httpx.Response(200, json=record))
    docker = AsyncMock()
    docker.check_container_running = AsyncMock()
    docker.__aenter__ = AsyncMock(return_value=docker)
    docker.__aexit__ = AsyncMock(return_value=False)

    with _patched(docker):
        await handler.sync_deployments()

    # it answers on its own, so it is promoted without touching the container
    docker.run_model_container.assert_not_awaited()
    assert b'"active"' in patch_route.calls[-1].request.read()


@respx.mock
async def test_a_deployment_without_a_container_is_not_resurrected() -> None:
    """Recovery restarts what this Satellite holds; it does not deploy from nothing.

    Creating a container for a deployment that has none would revive every deployment that
    ever failed on any Satellite — on the demo stand that was 19 abandoned ones at once.
    """
    handler = ModelServerHandler()
    _mock_platform(record=_platform_record() | {"status": "not_responding"})
    _mock_model_server()
    patch_route = respx.patch(
        f"{PLATFORM_URL}/satellites/v1/deployments/{DEPLOYMENT_ID}"
    ).mock(return_value=httpx.Response(200, json=_platform_record()))

    docker = AsyncMock()
    docker.check_container_running = AsyncMock(side_effect=ContainerNotFoundError(DEPLOYMENT_ID))
    docker.__aenter__ = AsyncMock(return_value=docker)
    docker.__aexit__ = AsyncMock(return_value=False)

    with _patched(docker):
        await handler.sync_deployments()

    docker.run_model_container.assert_not_awaited()
    assert b'"not_responding"' in patch_route.calls[-1].request.read()


@respx.mock
async def test_a_failed_deployment_is_not_touched() -> None:
    """A deploy that never worked needs a real redeploy, not a container restart."""
    handler = ModelServerHandler()
    _mock_platform(record=_platform_record() | {"status": "failed"})
    _mock_model_server()
    docker = _stopped_docker()

    with _patched(docker):
        await handler.sync_deployments()

    docker.run_model_container.assert_not_awaited()
    assert handler.deployments == {}


@respx.mock
async def test_a_running_container_is_left_alone() -> None:
    handler = ModelServerHandler()
    _mock_platform()
    _mock_model_server()
    docker = AsyncMock()
    docker.check_container_running = AsyncMock()
    docker.__aenter__ = AsyncMock(return_value=docker)
    docker.__aexit__ = AsyncMock(return_value=False)

    with _patched(docker):
        await handler.sync_deployments()

    # recreating a healthy container would drop live traffic for no reason
    docker.run_model_container.assert_not_awaited()
    assert DEPLOYMENT_ID in handler.deployments


async def test_model_containers_are_told_where_the_agent_is() -> None:
    """The callback address, built from the Agent's own host and port.

    It used to be assembled from the model server's port and a hostname with no network
    alias behind it, so it resolved to nothing. Nothing read the variable, so nothing broke
    — until something needed to call back.
    """
    from agent.clients.docker_client import AGENT_HOST, DockerService

    with patch("agent.clients.docker_client.aiodocker.Docker"):
        service = DockerService()
        service.client.containers.create_or_replace = AsyncMock()
        await service.run_model_container(image="img", name="sat-x", env={})
        config_arg = service.client.containers.create_or_replace.await_args.kwargs["config"]

    env = dict(entry.split("=", 1) for entry in config_arg["Env"])
    assert env["SATELLITE_AGENT_URL"] == f"http://{AGENT_HOST}:{config.AGENT_PORT}"
    assert str(config.MODEL_SERVER_PORT) not in env["SATELLITE_AGENT_URL"]


@pytest.mark.parametrize("method", ["run_model_container", "_container_for_model_cache_clean_up"])
async def test_model_containers_mount_the_shared_cache(method: str) -> None:
    """Without the volume every restart re-downloads — which is exactly what expires."""
    from agent.clients.docker_client import MODEL_CACHE_BIND, DockerService

    with patch("agent.clients.docker_client.aiodocker.Docker"):
        service = DockerService()
        service.client.containers.create_or_replace = AsyncMock()
        service.client.containers.create = AsyncMock()
        service.client.images.get = AsyncMock()

        if method == "run_model_container":
            await service.run_model_container(image="img", name="sat-x", env={})
            config_arg = service.client.containers.create_or_replace.await_args.kwargs["config"]
        else:
            await service._container_for_model_cache_clean_up("model-id")
            config_arg = service.client.containers.create.await_args.kwargs["config"]

    assert MODEL_CACHE_BIND in config_arg["HostConfig"]["Binds"]
