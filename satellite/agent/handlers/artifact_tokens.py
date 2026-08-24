"""Per-deployment tokens that let a model container ask the Agent for its artifact.

The token is derived from the Satellite's own credential rather than stored, which is what
makes it survive both restarts: the Agent keeps no state to lose, and a container that has
been sitting stopped for weeks still presents a token the Agent recognises.

It is not a Platform credential and grants nothing on its own — the Agent checks that the
token belongs to the deployment being asked about, so a container can only ever fetch its
own artifact, and only through the Agent.
"""

import hashlib
import hmac

from agent.settings import config


def mint(deployment_id: str) -> str:
    return hmac.new(
        config.SATELLITE_TOKEN.encode(), str(deployment_id).encode(), hashlib.sha256
    ).hexdigest()


def verify(deployment_id: str, token: str | None) -> bool:
    """Constant-time check that ``token`` was minted for this deployment."""
    if not token:
        return False
    return hmac.compare_digest(mint(deployment_id), token)
