import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from dataforce_studio.handlers.organizations import OrganizationHandler
from dataforce_studio.infra.dependencies import get_current_user
from dataforce_studio.models.auth import AuthUser
from dataforce_studio.schemas.organization import UpdateOrganizationMember, OrganizationMemberCreate

members_router = APIRouter(prefix="/members", tags=["organization-members"])

organization_handler = OrganizationHandler()


@members_router.get("/{organization_id}")
async def get_organization_members(
        organization_id: uuid.UUID,
        user: Annotated[AuthUser, Depends(get_current_user)]
):
    return await organization_handler.get_organization_members_data(organization_id)


@members_router.post("/")
async def add_member_to_organization(
        member: OrganizationMemberCreate,
        user: Annotated[AuthUser, Depends(get_current_user)]
):
    return await organization_handler.add_organization_member(member)


@members_router.patch("/{member_id}")
async def update_organization_member(
        member: UpdateOrganizationMember,
        user: Annotated[AuthUser, Depends(get_current_user)]
):
    return await organization_handler.update_organization_member_by_id(member)


@members_router.delete("/{member_id}")
async def remove_organization_member(
        member_id: uuid.UUID,
        user: Annotated[AuthUser, Depends(get_current_user)]
):
    return await organization_handler.delete_organization_member_by_id(member_id)
