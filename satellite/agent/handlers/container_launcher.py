"""Building the model-server container for a deployment.

Shared by the deploy task and by startup reconciliation, so both build the container the
same way.

The container is given no download link. A presigned URL expires in hours while a container
lives for weeks, and Docker will not let an environment change afterwards — so a container
holding one is dead the moment it outlives it. Instead it carries a token and asks the Agent
for a URL when it downloads.
"""

import logging
from uuid import UUID

from aiodocker.containers import DockerContainer

from agent.clients import DockerService, PlatformClient
from agent.handlers import artifact_tokens
from agent.schemas import Deployment
from agent.settings import config

logger = logging.getLogger(__name__)


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


async def container_env(platform: PlatformClient, deployment: Deployment) -> dict[str, str]:
    env: dict[str, str] = {
        # not a URL: what the container proves itself with when it asks for one
        "MODEL_ARTIFACT_TOKEN": artifact_tokens.mint(str(deployment.id)),
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
    """Create (or replace) the deployment's model container."""
    return await docker.run_model_container(
        image=config.MODEL_IMAGE,
        name=f"sat-{deployment.id}",
        container_port=config.MODEL_SERVER_PORT,
        labels={
            "df.deployment_id": str(deployment.id),
            # the cache key the container will use, so undeploy can clean the same entry
            "df.model_id": str(deployment.artifact_id),
        },
        env=await container_env(platform, deployment),
    )
