from fastapi import APIRouter, Depends

from dataforce_studio.handlers.orbits import OrbitHandler
from dataforce_studio.infra.dependencies import is_user_authenticated
from dataforce_studio.schemas.orbit import (
    OrbitMember,
    OrbitMemberCreate,
    UpdateOrbitMember,
)

orbit_members_router = APIRouter(
    prefix="/orbits/{orbit_id}/members",
    tags=["orbits-members"]
)

orbit_handler = OrbitHandler()


@orbit_members_router.get("", response_model=list[OrbitMember])
async def get_orbit_members(
        orbit_id: int,
) -> list[OrbitMember]:
    return await orbit_handler.get_orbit_members(orbit_id)


@orbit_members_router.post("", response_model=OrbitMember)
async def add_member_to_orbit(member: OrbitMemberCreate) -> OrbitMember:
    return await orbit_handler.create_orbit_member(member)


@orbit_members_router.patch("/{member_id}", response_model=OrbitMember)
async def update_orbit_member(member: UpdateOrbitMember) -> OrbitMember:
    return await orbit_handler.update_orbit_member(member)


@orbit_members_router.delete("/{member_id}", status_code=204)
async def remove_orbit_member(member_id: int) -> None:
    return await orbit_handler.delete_orbit_member(member_id)
