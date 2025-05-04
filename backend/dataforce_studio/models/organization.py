import uuid
from enum import StrEnum

from pydantic import BaseModel, HttpUrl

from dataforce_studio.models.base import BaseOrmConfig


class OrgRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class OrganizationMember(BaseModel, BaseOrmConfig):
    id: uuid.UUID
    user_id: uuid.UUID
    organization_id: uuid.UUID
    role: OrgRole


class Organization(BaseModel, BaseOrmConfig):
    id: uuid.UUID
    name: str
    logo: HttpUrl | None = None
