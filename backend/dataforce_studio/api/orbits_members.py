import uuid

from fastapi import APIRouter, Depends

from dataforce_studio.handlers.orbits import OrbitHandler
from dataforce_studio.infra.dependencies import is_user_authenticated
from dataforce_studio.schemas.orbit import (
    OrbitMember,
    OrbitMemberCreate,
    UpdateOrbitMember,
)

orbit_members_router = APIRouter(
    prefix="/orbits/members",
    tags=["orbits-members"],
    dependencies=[Depends(is_user_authenticated)],
)
orbit_router = APIRouter(
    prefix="/orbits",
    tags=["orbits-members"],
    dependencies=[Depends(is_user_authenticated)],
)

orbit_handler = OrbitHandler()


@orbit_router.get("/{orbit_id}/members", response_model=list[OrbitMember])
async def get_orbit_members(
    orbit_id: uuid.UUID,
) -> list[OrbitMember]:
    return await orbit_handler.get_orbit_members(orbit_id)


@orbit_members_router.post("", response_model=OrbitMember)
async def add_member_to_robit(member: OrbitMemberCreate) -> OrbitMember:
    return await orbit_handler.create_orbit_member(member)


@orbit_members_router.patch("", response_model=OrbitMember)
async def update_orbit_member(member: UpdateOrbitMember) -> OrbitMember:
    return await orbit_handler.update_orbit_member(member)


@orbit_members_router.delete("/{member_id}", status_code=204)
async def remove_orbit_member(member_id: uuid.UUID) -> None:
    return await orbit_handler.delete_orbit_member(member_id)
