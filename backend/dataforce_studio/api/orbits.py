from fastapi import APIRouter, Depends, status

from dataforce_studio.handlers.orbits import OrbitHandler
from dataforce_studio.infra.dependencies import is_user_authenticated
from dataforce_studio.schemas.orbit import Orbit, OrbitCreate, OrbitDetails, OrbitUpdate

orbits_router = APIRouter(
    prefix="/orbits",
    tags=["orbits"],
    dependencies=[Depends(is_user_authenticated)],
)
organization_orbits_router = APIRouter(
    tags=["orbits"],
    dependencies=[Depends(is_user_authenticated)],
)

orbit_handler = OrbitHandler()


@organization_orbits_router.get("/{organization_id}/orbits")
async def get_organization_orbits(organization_id: int) -> list[Orbit]:
    return await orbit_handler.get_organization_orbits(organization_id)


@orbits_router.get("/{orbit_id}", response_model=OrbitDetails)
async def get_orbit_details(orbit_id: int) -> OrbitDetails:
    return await orbit_handler.get_orbit(orbit_id)


@orbits_router.post("", response_model=Orbit)
async def create_orbit(orbit: OrbitCreate) -> Orbit:
    return await orbit_handler.create_organization_orbit(orbit)


@orbits_router.patch("", response_model=Orbit)
async def update_orbit(orbit: OrbitUpdate) -> Orbit:
    return await orbit_handler.update_orbit(orbit)


@orbits_router.delete("/{orbit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_orbit(orbit_id: int) -> None:
    return await orbit_handler.delete_orbit(orbit_id)
