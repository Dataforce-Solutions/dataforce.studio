from fastapi import APIRouter, status

from dataforce_studio.handlers.organizations import OrganizationHandler
from dataforce_studio.schemas.organization import (
    OrganizationMember,
    OrganizationMemberCreate,
    UpdateOrganizationMember,
)

members_router = APIRouter(
    prefix="/{organization_id}/members",
    tags=["organization-members"]
)

organization_handler = OrganizationHandler()


@members_router.get("")
async def get_organization_members(organization_id: int) -> list[OrganizationMember]:
    return await organization_handler.get_organization_members_data(organization_id)


@members_router.post("")
async def add_member_to_organization(
        member: OrganizationMemberCreate,
) -> OrganizationMember:
    return await organization_handler.add_organization_member(member)


@members_router.patch("/{member_id}")
async def update_organization_member(
        member_id: int,
        member: UpdateOrganizationMember,
) -> OrganizationMember | None:
    return await organization_handler.update_organization_member_by_id(member_id, member)


@members_router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_organization_member(member_id: int) -> None:
    return await organization_handler.delete_organization_member_by_id(member_id)
