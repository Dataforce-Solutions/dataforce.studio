import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr

from dataforce_studio.schemas.organization import OrgRole


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


class OrganizationInvites(BaseModel):
    notes: list[OrganizationInvite]
