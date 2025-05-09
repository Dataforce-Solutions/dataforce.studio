import uuid

from pydantic import BaseModel

from dataforce_studio.models.organization import OrgRole
from dataforce_studio.schemas.user import UserResponse


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
