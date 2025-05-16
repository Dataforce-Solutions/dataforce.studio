import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr

from dataforce_studio.schemas.base import BaseOrmConfig
from dataforce_studio.schemas.organization import OrgRole


class CreateOrganizationInvite(BaseModel):
    email: EmailStr
    role: OrgRole
    organization_id: uuid.UUID
    invited_by: uuid.UUID


class OrganizationInvite(BaseModel, BaseOrmConfig):
    id: uuid.UUID
    email: EmailStr
    role: OrgRole
    organization_id: uuid.UUID
    invited_by: uuid.UUID
    created_at: datetime


class OrganizationInvites(BaseModel):
    notes: list[OrganizationInvite]
