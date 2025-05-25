from fastapi import APIRouter, status, Request

from dataforce_studio.handlers.organizations import OrganizationHandler
from dataforce_studio.handlers.permissions import PermissionsHandler
from dataforce_studio.schemas.organization import (
    OrganizationMember,
    OrganizationMemberCreate,
    UpdateOrganizationMember,
)
from dataforce_studio.schemas.permissions import Resources, ResourceAction

members_router = APIRouter(
    prefix="/{organization_id}/members", tags=["organization-members"]
)

organization_handler = OrganizationHandler()
permissions_handler = PermissionsHandler()


@members_router.get("")
async def get_organization_members(
    request: Request, organization_id: int
) -> list[OrganizationMember]:
    await permissions_handler.check_organization_permission(
        organization_id,
        request.user.id,
        Resources.ORGANIZATION_USER,
        ResourceAction.LIST,
    )
    return await organization_handler.get_organization_members_data(organization_id)


@members_router.post("")
async def add_member_to_organization(
    request: Request,
    organization_id: int,
    member: OrganizationMemberCreate,
) -> OrganizationMember:
    await permissions_handler.check_organization_permission(
        organization_id,
        request.user.id,
        Resources.ORGANIZATION_USER,
        ResourceAction.CREATE,
    )
    return await organization_handler.add_organization_member(member)


@members_router.patch("/{member_id}")
async def update_organization_member(
    request: Request,
    organization_id: int,
    member_id: int,
    member: UpdateOrganizationMember,
) -> OrganizationMember | None:
    await permissions_handler.check_organization_permission(
        organization_id,
        request.user.id,
        Resources.ORGANIZATION_USER,
        ResourceAction.CREATE,
    )
    return await organization_handler.update_organization_member_by_id(
        member_id, member
    )


@members_router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_organization_member(
    request: Request, organization_id: int, member_id: int
) -> None:
    await permissions_handler.check_organization_permission(
        organization_id,
        request.user.id,
        Resources.ORGANIZATION_USER,
        ResourceAction.DELETE,
    )
    return await organization_handler.delete_organization_member_by_id(member_id)
