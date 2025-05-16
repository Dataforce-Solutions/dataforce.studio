import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, EmailStr, HttpUrl

from dataforce_studio.schemas.base import BaseOrmConfig
from dataforce_studio.schemas.user import UserOut


class OrgRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class CreateOrganizationInvite(BaseModel):
    email: EmailStr
    role: OrgRole
    organization_id: uuid.UUID
    invited_by: uuid.UUID


class OrganizationInvite(BaseModel):
    id: uuid.UUID
    email: EmailStr
    role: OrgRole
    organization_id: uuid.UUID
    invited_by: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class UpdateOrganizationMember(BaseModel):
    id: uuid.UUID
    role: OrgRole


class OrganizationMember(BaseModel, BaseOrmConfig):
    id: uuid.UUID
    organization_id: uuid.UUID
    role: OrgRole
    user: UserOut


class OrganizationMemberCreate(BaseModel):
    user_id: uuid.UUID
    organization_id: uuid.UUID
    role: OrgRole


class Organization(BaseModel, BaseOrmConfig):
    id: uuid.UUID
    name: str
    logo: HttpUrl | None = None

    class Config:
        from_attributes = True


class OrganizationSwitcher(Organization):
    role: OrgRole | None = None


class OrganizationDetails(Organization):
    created_at: datetime
    updated_at: datetime | None = None
    invites: list[OrganizationInvite]
    members: list[OrganizationMember]

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True
