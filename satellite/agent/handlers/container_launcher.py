"""Building the model-server container for a deployment.

Shared by the deploy task and by startup reconciliation. Both have to build the container
the same way, and — more importantly — both have to mint the artifact URL at the moment the
container is created: it is presigned, it is baked into the container's environment, and
Docker will not let anyone change an environment afterwards. A container recreated from a
stale URL cannot download its model and never comes back up.
"""

import hashlib
import logging
from urllib.parse import urlparse
from uuid import UUID

from aiodocker.containers import DockerContainer

from agent.clients import DockerService, PlatformClient
from agent.schemas import Deployment
from agent.settings import config

logger = logging.getLogger(__name__)


def model_id_from_url(url: str) -> str:
    """Cache key of an artifact: its path, without the signature that changes per request."""
    parsed_url = urlparse(url)
    url_path = parsed_url.path.split("?")[0]
    return hashlib.md5(url_path.encode()).hexdigest()


async def secrets_env(
    platform: PlatformClient, secrets_payload: dict[str, str] | None
) -> dict[str, str]:
    """Resolve secret-backed environment variables, skipping the ones that cannot be read."""
    resolved: dict[str, str] = {}
    if not isinstance(secrets_payload, dict):
        return resolved
    for key, secret_id in secrets_payload.items():
        try:
            secret = await platform.get_orbit_secret(UUID(secret_id))
            resolved[str(key)] = str(secret.get("value", ""))
        except Exception:
            continue
    return resolved


async def container_env(
    platform: PlatformClient, presigned_url: str, deployment: Deployment
) -> dict[str, str]:
    env: dict[str, str] = {
        "MODEL_ARTIFACT_URL": str(presigned_url),
        "DEPLOYMENT_ID": str(deployment.id),
        "MODEL_NAME": deployment.artifact_name,
    }
    if config.OTEL_EXPORTER_OTLP_ENDPOINT:
        env["OTEL_EXPORTER_OTLP_ENDPOINT"] = config.OTEL_EXPORTER_OTLP_ENDPOINT

    env.update(await secrets_env(platform, deployment.env_variables_secrets))
    env.update(deployment.env_variables or {})
    return env


async def launch_model_container(
    platform: PlatformClient, docker: DockerService, deployment: Deployment
) -> DockerContainer:
    """Create (or replace) the deployment's model container with a freshly signed artifact URL."""
    presigned_url = await platform.get_artifact_download_url(UUID(deployment.artifact_id))
    return await docker.run_model_container(
        image=config.MODEL_IMAGE,
        name=f"sat-{deployment.id}",
        container_port=config.MODEL_SERVER_PORT,
        labels={
            "df.deployment_id": str(deployment.id),
            "df.model_id": model_id_from_url(presigned_url),
        },
        env=await container_env(platform, presigned_url, deployment),
    )
