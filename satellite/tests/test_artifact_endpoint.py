"""The Agent's artifact endpoint: the model container's only way to a download link.

A presigned URL expires in hours and a container lives for weeks, so the container is given
no link of its own — it asks for one when it downloads. These tests pin who may ask.
"""

import uuid
from datetime import UTC, datetime

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from agent.clients import PlatformClient
from agent.settings import config

from agent.agent_api import create_agent_app
from agent.handlers import artifact_tokens
from agent.handlers.artifact_urls import presigned_expiry
from agent.schemas import ArtifactDownload

DEPLOYMENT_ID = str(uuid.uuid4())
OTHER_DEPLOYMENT_ID = str(uuid.uuid4())
ARTIFACT_ID = str(uuid.uuid4())
SIGNED_URL = "https://s3.example.com/a/model.luml?X-Amz-Signature=abc"


async def _authorize(_: str) -> bool:
    return True


def _client(resolve=None) -> TestClient:  # noqa: ANN001 — test helper
    async def default_resolve(deployment_id: uuid.UUID) -> ArtifactDownload:
        return ArtifactDownload(url=SIGNED_URL, artifact_id=ARTIFACT_ID)

    return TestClient(create_agent_app(_authorize, resolve or default_resolve))


def _url(deployment_id: str = DEPLOYMENT_ID) -> str:
    return f"/satellites/deployments/{deployment_id}/artifact"


def test_a_container_gets_a_url_signed_for_this_request() -> None:
    response = _client().get(
        _url(), headers={"X-Artifact-Token": artifact_tokens.mint(DEPLOYMENT_ID)}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["url"] == SIGNED_URL
    # the cache key: it identifies the model, unlike the URL whose signature rotates
    assert body["artifact_id"] == ARTIFACT_ID


def test_without_a_token_nothing_is_handed_out() -> None:
    assert _client().get(_url()).status_code == 403


def test_a_token_for_another_deployment_is_refused() -> None:
    """The token binds to one deployment, so a container cannot fetch someone else's model."""
    response = _client().get(
        _url(), headers={"X-Artifact-Token": artifact_tokens.mint(OTHER_DEPLOYMENT_ID)}
    )

    assert response.status_code == 403


def test_a_deployment_this_satellite_does_not_host_is_a_404() -> None:
    async def resolve(deployment_id: uuid.UUID) -> ArtifactDownload:
        raise KeyError(deployment_id)

    response = _client(resolve).get(
        _url(), headers={"X-Artifact-Token": artifact_tokens.mint(DEPLOYMENT_ID)}
    )

    assert response.status_code == 404


def test_a_platform_failure_is_reported_as_a_gateway_error() -> None:
    async def resolve(deployment_id: uuid.UUID) -> ArtifactDownload:
        raise RuntimeError("platform is down")

    response = _client(resolve).get(
        _url(), headers={"X-Artifact-Token": artifact_tokens.mint(DEPLOYMENT_ID)}
    )

    assert response.status_code == 502


def test_tokens_survive_a_restart_of_either_side() -> None:
    """Derived from the Satellite credential, not stored: nothing is lost by restarting.

    A container that sat stopped for weeks still presents a token the Agent recognises, and
    an Agent that just came up has no table to have forgotten.
    """
    assert artifact_tokens.mint(DEPLOYMENT_ID) == artifact_tokens.mint(DEPLOYMENT_ID)
    assert artifact_tokens.mint(DEPLOYMENT_ID) != artifact_tokens.mint(OTHER_DEPLOYMENT_ID)
    assert artifact_tokens.verify(DEPLOYMENT_ID, artifact_tokens.mint(DEPLOYMENT_ID))
    assert not artifact_tokens.verify(DEPLOYMENT_ID, "")
    assert not artifact_tokens.verify(DEPLOYMENT_ID, None)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://s3/x?X-Amz-Date=20260818T131044Z&X-Amz-Expires=43200",
            datetime(2026, 8, 19, 1, 10, 44, tzinfo=UTC),
        ),
        ("https://s3/x?X-Amz-Date=20260818T131044Z", None),  # no lifetime stated
        ("https://s3/x", None),  # not a presigned URL at all
        ("https://s3/x?X-Amz-Date=nonsense&X-Amz-Expires=43200", None),
    ],
)
def test_presigned_expiry_is_read_when_it_is_there(url: str, expected: datetime | None) -> None:
    assert presigned_expiry(url) == expected


@respx.mock
async def test_the_resolver_signs_a_url_for_a_deployment_this_satellite_hosts() -> None:
    """Scoping is the Platform's: its satellite-scoped endpoint 404s on someone else's."""
    from agent.main import _artifact_resolver

    platform_url = str(config.PLATFORM_URL).rstrip("/")
    record = {
        "id": DEPLOYMENT_ID,
        "orbit_id": str(uuid.uuid4()),
        "satellite_id": str(uuid.uuid4()),
        "satellite_name": "sat",
        "name": "iris",
        "artifact_id": ARTIFACT_ID,
        "artifact_name": "iris",
        "collection_id": str(uuid.uuid4()),
        "status": "active",
        "created_at": "2026-08-18T13:10:44Z",
    }
    respx.get(f"{platform_url}/satellites/v1/deployments/{DEPLOYMENT_ID}").mock(
        return_value=httpx.Response(200, json=record)
    )
    respx.get(f"{platform_url}/satellites/v1/artifacts/{ARTIFACT_ID}/download-url").mock(
        return_value=httpx.Response(
            200, json={"url": "https://s3/x?X-Amz-Date=20260818T131044Z&X-Amz-Expires=43200"}
        )
    )

    async with PlatformClient(str(config.PLATFORM_URL), "token") as platform:
        artifact = await _artifact_resolver(platform)(uuid.UUID(DEPLOYMENT_ID))

    assert artifact.artifact_id == ARTIFACT_ID
    assert artifact.expires_at == datetime(2026, 8, 19, 1, 10, 44, tzinfo=UTC)


@respx.mock
async def test_the_resolver_turns_an_unknown_deployment_into_a_404() -> None:
    """Not a 502: the Platform saying "no such deployment here" is an answer, not a fault."""
    from agent.main import _artifact_resolver

    platform_url = str(config.PLATFORM_URL).rstrip("/")
    respx.get(f"{platform_url}/satellites/v1/deployments/{DEPLOYMENT_ID}").mock(
        return_value=httpx.Response(404, json={"detail": "Deployment not found"})
    )

    async with PlatformClient(str(config.PLATFORM_URL), "token") as platform:
        with pytest.raises(KeyError):
            await _artifact_resolver(platform)(uuid.UUID(DEPLOYMENT_ID))
