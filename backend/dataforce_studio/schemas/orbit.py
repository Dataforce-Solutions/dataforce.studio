import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel

from dataforce_studio.schemas.base import BaseOrmConfig
from dataforce_studio.schemas.user import UserOut


class OrbitRole(StrEnum):
    ADMIN = "admin"
    MEMBER = "member"
    # VIEWER = "viewer"


class Orbit(BaseModel, BaseOrmConfig):
    id: uuid.UUID
    name: str
    organization_id: uuid.UUID


class OrbitDetails(Orbit):
    members: list["OrbitMember"] | None = None
    created_at: datetime
    updated_at: datetime | None = None


class OrbitUpdate(BaseModel, BaseOrmConfig):
    id: uuid.UUID
    name: str


class OrbitCreate(BaseModel, BaseOrmConfig):
    name: str
    organization_id: uuid.UUID


class OrbitMemberCreate(BaseModel):
    user_id: uuid.UUID
    orbit_id: uuid.UUID
    role: OrbitRole


class UpdateOrbitMember(BaseModel):
    id: uuid.UUID
    role: OrbitRole


class OrbitMember(BaseModel, BaseOrmConfig):
    id: uuid.UUID
    orbit_id: uuid.UUID
    role: OrbitRole
    user: UserOut
    created_at: datetime
    updated_at: datetime | None = None
