"""Per-deployment tokens that let a model container ask the Agent for its artifact.

Derived from the Satellite credential rather than stored, so it survives restarts on
both sides; it is bound to one deployment and grants nothing beyond its own artifact.
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
