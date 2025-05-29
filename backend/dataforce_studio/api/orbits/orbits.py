from fastapi import APIRouter, status

from dataforce_studio.handlers.orbits import OrbitHandler
from dataforce_studio.schemas.orbit import Orbit, OrbitCreate, OrbitDetails, OrbitUpdate

orbits_router = APIRouter(prefix="/orbits/{orbit_id}", tags=["orbits"])
organization_orbits_router = APIRouter(
    prefix="/{organization_id}/orbits", tags=["orbits"]
)

orbit_handler = OrbitHandler()


@organization_orbits_router.get("")
async def get_organization_orbits(organization_id: int) -> list[Orbit]:
    return await orbit_handler.get_organization_orbits(organization_id)


@organization_orbits_router.post("", response_model=Orbit)
async def create_orbit(organization_id: int, orbit: OrbitCreate) -> Orbit:
    return await orbit_handler.create_organization_orbit(organization_id, orbit)


@orbits_router.get("", response_model=OrbitDetails)
async def get_orbit_details(orbit_id: int) -> OrbitDetails:
    return await orbit_handler.get_orbit(orbit_id)


@orbits_router.patch("", response_model=Orbit)
async def update_orbit(orbit_id: int, orbit: OrbitUpdate) -> Orbit:
    return await orbit_handler.update_orbit(orbit_id, orbit)


@orbits_router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_orbit(orbit_id: int) -> None:
    return await orbit_handler.delete_orbit(orbit_id)
