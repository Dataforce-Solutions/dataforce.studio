from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, EmailStr, HttpUrl

from dataforce_studio.schemas.base import BaseOrmConfig
from dataforce_studio.schemas.user import UserOut


class OrgRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class Organization(BaseModel, BaseOrmConfig):
    id: int
    name: str
    logo: HttpUrl | None = None


class OrganizationSwitcher(Organization):
    role: OrgRole | None = None


class CreateOrganizationInvite(BaseModel):
    email: EmailStr
    role: OrgRole
    organization_id: int
    invited_by: int


class OrganizationInvite(BaseModel, BaseOrmConfig):
    id: int
    email: EmailStr
    role: OrgRole
    organization_id: int
    invited_by: UserOut | None = None
    created_at: datetime


class UserInvite(OrganizationInvite):
    organization: Organization | None = None


class UpdateOrganizationMember(BaseModel):
    role: OrgRole


class OrganizationMember(BaseModel, BaseOrmConfig):
    id: int
    organization_id: int
    role: OrgRole
    user: UserOut


class OrganizationMemberCreate(BaseModel):
    user_id: int
    organization_id: int
    role: OrgRole

class OrganizationDetails(Organization, BaseOrmConfig):
    created_at: datetime
    updated_at: datetime | None = None
    invites: list[OrganizationInvite]
    members: list[OrganizationMember]
