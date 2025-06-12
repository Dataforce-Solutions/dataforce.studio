from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, EmailStr, Field, HttpUrl, field_validator

from dataforce_studio.schemas.base import BaseOrmConfig
from dataforce_studio.schemas.orbit import Orbit
from dataforce_studio.schemas.user import UserOut


class OrgRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class OrganizationCreate(BaseModel):
    name: str
    logo: HttpUrl | None = None


class OrganizationUpdate(BaseModel):
    id: int | None = None
    name: str | None = None
    logo: HttpUrl | str | None = None


class Organization(BaseModel, BaseOrmConfig):
    id: int
    name: str
    logo: HttpUrl | None = None
    created_at: datetime
    updated_at: datetime | None = None


class OrganizationSwitcher(Organization):
    role: OrgRole | None = None


class CreateOrganizationInviteIn(BaseModel):
    email: EmailStr
    role: OrgRole
    organization_id: int

    @field_validator("role")
    @classmethod
    def forbid_owner(cls, value: OrgRole) -> OrgRole:
        if value == OrgRole.OWNER:
            raise ValueError("Role 'OWNER' cant be assigned")
        return value


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
    invited_by_user: UserOut | None = None
    organization: Organization | None = None
    created_at: datetime


class UserInvite(OrganizationInvite):
    organization: Organization | None = None


class UpdateOrganizationMember(BaseModel):
    role: OrgRole

    @field_validator("role")
    @classmethod
    def forbid_owner(cls, value: OrgRole) -> OrgRole:
        if value == OrgRole.OWNER:
            raise ValueError("Role 'OWNER' cant be assigned")
        return value


class OrganizationMember(BaseModel, BaseOrmConfig):
    id: int
    organization_id: int
    role: OrgRole
    user: UserOut


class OrganizationMemberCreate(BaseModel):
    user_id: int
    organization_id: int
    role: OrgRole

    @field_validator("role")
    @classmethod
    def forbid_owner(cls, value: OrgRole) -> OrgRole:
        if value == OrgRole.OWNER:
            raise ValueError("Role 'OWNER' cant be assigned")
        return value


class OrganizationDetails(Organization):
    invites: list[OrganizationInvite]
    members: list[OrganizationMember]
    orbits: list[Orbit]
    members_limit: int = 0
    orbits_limit: int = 0
    total_orbits: int = 0
    total_members: int = 0
    members_by_role: dict[str, int] = Field(default_factory=dict)
