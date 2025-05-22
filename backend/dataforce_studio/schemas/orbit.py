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
    id: int
    name: str
    organization_id: uuid.UUID


class OrbitDetails(Orbit):
    members: list["OrbitMember"] | None = None
    created_at: datetime
    updated_at: datetime | None = None


class OrbitUpdate(BaseModel, BaseOrmConfig):
    id: int | None = None
    name: str


class OrbitCreate(BaseModel, BaseOrmConfig):
    name: str
    organization_id: int | None = None


class OrbitMemberCreate(BaseModel):
    user_id: int
    orbit_id: int
    role: OrbitRole


class UpdateOrbitMember(BaseModel):
    id: int
    role: OrbitRole


class OrbitMember(BaseModel, BaseOrmConfig):
    id: int
    orbit_id: int
    role: OrbitRole
    user: UserOut
    created_at: datetime
    updated_at: datetime | None = None
