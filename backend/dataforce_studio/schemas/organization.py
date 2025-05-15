import uuid
from enum import StrEnum

from pydantic import BaseModel, HttpUrl

from dataforce_studio.models.base import BaseOrmConfig
from dataforce_studio.schemas.user import UserResponse


class OrgRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class UpdateOrganizationMember(BaseModel):
    id: uuid.UUID
    role: OrgRole


class OrganizationMember(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    role: OrgRole
    user: UserResponse

    class Config:
        from_attributes = True


class OrganizationMemberCreate(BaseModel):
    user_id: uuid.UUID
    organization_id: uuid.UUID
    role: OrgRole


class Organization(BaseModel, BaseOrmConfig):
    id: uuid.UUID
    name: str
    logo: HttpUrl | None = None
