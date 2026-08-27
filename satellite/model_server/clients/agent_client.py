"""Asking the Satellite Agent where to download this deployment's artifact from.

The container holds no download link of its own. A presigned URL expires in hours while a
container lives for weeks, so the link is fetched at the moment it is used and never stored
— which is what makes a restart weeks later survivable.
"""

import logging
import os
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# The read budget must exceed the Agent resolver's own worst case: answering means two
# sequential Platform calls, each with a 30-second budget of its own. A tighter limit
# here would turn two individually healthy slow calls into "Agent unreachable" and
# crash-loop a container that only had to wait a little longer.
_TIMEOUT = httpx.Timeout(connect=10.0, read=90.0, write=10.0, pool=10.0)


class ArtifactResolutionError(RuntimeError):
    """The Agent could not say where the artifact is."""


@dataclass(frozen=True)
class ArtifactRef:
    url: str
    artifact_id: str


class AgentClient:
    """Reads its address and credentials from the environment the Agent set up."""

    def __init__(
        self,
        base_url: str | None = None,
        deployment_id: str | None = None,
        token: str | None = None,
    ) -> None:
        self._base_url = (base_url or os.getenv("SATELLITE_AGENT_URL", "")).rstrip("/")
        self._deployment_id = deployment_id or os.getenv("DEPLOYMENT_ID", "")
        self._token = token or os.getenv("MODEL_ARTIFACT_TOKEN", "")

    @property
    def configured(self) -> bool:
        return bool(self._base_url and self._deployment_id and self._token)

    def fetch_artifact(self) -> ArtifactRef:
        if not self.configured:
            raise ArtifactResolutionError(
                "Cannot ask the Agent for the artifact: SATELLITE_AGENT_URL, DEPLOYMENT_ID "
                "or MODEL_ARTIFACT_TOKEN is missing from the environment."
            )

        url = f"{self._base_url}/satellites/deployments/{self._deployment_id}/artifact"
        logger.info("Asking the Agent for a download URL...")
        try:
            # trust_env=False: this is an internal call carrying the artifact token, and
            # deployment environment variables can set HTTP_PROXY/ALL_PROXY — a proxy
            # must neither see the token nor stand between the container and its Agent.
            response = httpx.get(
                url,
                headers={"X-Artifact-Token": self._token},
                timeout=_TIMEOUT,
                trust_env=False,
            )
        except httpx.HTTPError as error:
            raise ArtifactResolutionError(
                f"Agent unreachable at {self._base_url}: {error}"
            ) from error

        if response.status_code == 403:
            raise ArtifactResolutionError(
                "The Agent rejected this container's artifact token. The deployment may have "
                "been recreated; redeploy it."
            )
        if response.status_code == 404:
            raise ArtifactResolutionError(
                f"The Agent does not host deployment '{self._deployment_id}'."
            )
        if response.status_code >= 400:
            raise ArtifactResolutionError(
                f"The Agent answered HTTP {response.status_code}: {response.text[:200]}"
            )

        payload = response.json()
        artifact_id = payload.get("artifact_id")
        download_url = payload.get("url")
        if not artifact_id or not download_url:
            raise ArtifactResolutionError(f"Incomplete artifact response: {payload}")
        return ArtifactRef(url=download_url, artifact_id=str(artifact_id))
