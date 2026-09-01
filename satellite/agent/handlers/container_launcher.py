"""Building the model-server container for a deployment.

Shared by the deploy task and by startup reconciliation, so both build the container the
same way.
"""

import logging
from uuid import UUID

from aiodocker.containers import DockerContainer

from agent.clients import DockerService, PlatformClient
from agent.handlers import artifact_tokens
from agent.schemas import Deployment
from agent.settings import config

logger = logging.getLogger(__name__)

# Bump whenever containers built the old way must be replaced rather than kept.
#   (no label) — presigned MODEL_ARTIFACT_URL in the environment, one shared cache volume
#   "2"        — artifact token instead of a URL, cache volume private to the artifact
LAUNCHER_PROTOCOL_LABEL = "df.launcher_protocol"
LAUNCHER_PROTOCOL = "2"


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
    env: dict[str, str] = {}
    env.update(await secrets_env(platform, deployment.env_variables_secrets))
    env.update(deployment.env_variables or {})

    # applied on top of deployment-supplied variables, never under them
    internal: dict[str, str] = {
        "MODEL_ARTIFACT_TOKEN": artifact_tokens.mint(str(deployment.id)),
        "MODEL_ARTIFACT_ID": str(deployment.artifact_id),
        "DEPLOYMENT_ID": str(deployment.id),
        "MODEL_NAME": deployment.artifact_name,
    }
    if config.OTEL_EXPORTER_OTLP_ENDPOINT:
        internal["OTEL_EXPORTER_OTLP_ENDPOINT"] = config.OTEL_EXPORTER_OTLP_ENDPOINT

    overridden = sorted(set(env) & set(internal))
    if overridden:
        logger.warning(
            f"[container_env] Deployment '{deployment.id}' supplied reserved environment "
            f"variables, ignoring them: {overridden}"
        )

    env.update(internal)
    return env


async def launch_model_container(
    platform: PlatformClient, docker: DockerService, deployment: Deployment
) -> DockerContainer:
    """Create (or replace) the deployment's model container."""
    return await docker.run_model_container(
        image=config.MODEL_IMAGE,
        name=f"sat-{deployment.id}",
        model_id=str(deployment.artifact_id),
        container_port=config.MODEL_SERVER_PORT,
        labels={
            "df.deployment_id": str(deployment.id),
            "df.model_id": str(deployment.artifact_id),
            LAUNCHER_PROTOCOL_LABEL: LAUNCHER_PROTOCOL,
        },
        env=await container_env(platform, deployment),
    )
