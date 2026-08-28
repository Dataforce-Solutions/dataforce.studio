from uuid import UUID

from pydantic import BaseModel

MONITORING_READ_SCOPE = "monitoring:read"
# Reserved for a Platform-minted write scope; acknowledging rides the read session for now.
MONITORING_WRITE_SCOPE = "monitoring:write"


class MonitoringTokenClaims(BaseModel):
    deployment_id: UUID
    satellite_id: UUID
    user_id: UUID
    scope: str
    jti: UUID
    exp: int


class MonitoringIntrospection(BaseModel):
    active: bool
    claims: MonitoringTokenClaims | None = None


class MonitoringSessionInfo(BaseModel):
    deployment_id: UUID
    scope: str
