from fastapi import APIRouter, Request

from dataforce_studio.handlers.orbits import OrbitHandler
from dataforce_studio.handlers.permissions import PermissionsHandler
from dataforce_studio.schemas.orbit import (
    OrbitMember,
    OrbitMemberCreate,
    UpdateOrbitMember,
)
from dataforce_studio.schemas.permissions import Resources, ResourceAction

orbit_members_router = APIRouter(
    prefix="/{organization_id}/orbits/{orbit_id}/members", tags=["orbits-members"]
)

orbit_handler = OrbitHandler()
permissions_handler = PermissionsHandler()


@orbit_members_router.get("", response_model=list[OrbitMember])
async def get_orbit_members(
    request: Request,
    organization_id: int,
    orbit_id: int,
) -> list[OrbitMember]:
    await permissions_handler.check_organization_permission(
        organization_id,
        request.user.id,
        Resources.ORBIT_USER,
        ResourceAction.LIST,
    )
    return await orbit_handler.get_orbit_members(orbit_id)


@orbit_members_router.post("", response_model=OrbitMember)
async def add_member_to_orbit(
    request: Request, organization_id: int, member: OrbitMemberCreate
) -> OrbitMember:
    await permissions_handler.check_organization_permission(
        organization_id,
        request.user.id,
        Resources.ORBIT_USER,
        ResourceAction.CREATE,
    )
    return await orbit_handler.create_orbit_member(member)


@orbit_members_router.patch("/{member_id}", response_model=OrbitMember)
async def update_orbit_member(
    request: Request, organization_id: int, member: UpdateOrbitMember
) -> OrbitMember:
    await permissions_handler.check_organization_permission(
        organization_id,
        request.user.id,
        Resources.ORBIT_USER,
        ResourceAction.UPDATE,
    )
    return await orbit_handler.update_orbit_member(member)


@orbit_members_router.delete("/{member_id}", status_code=204)
async def remove_orbit_member(
    request: Request, organization_id: int, member_id: int
) -> None:
    await permissions_handler.check_organization_permission(
        organization_id,
        request.user.id,
        Resources.ORBIT_USER,
        ResourceAction.DELETE,
    )
    return await orbit_handler.delete_orbit_member(member_id)
