from fastapi import APIRouter, Request, status

from dataforce_studio.handlers.orbits import OrbitHandler
from dataforce_studio.infra.endpoint_responses import endpoint_responses
from dataforce_studio.schemas.orbit import (
    Orbit,
    OrbitCreateIn,
    OrbitDetails,
    OrbitUpdate,
)

organization_orbits_router = APIRouter(
    prefix="/{organization_id}/orbits", tags=["orbits"]
)

orbit_handler = OrbitHandler()


@organization_orbits_router.get("", responses=endpoint_responses)
async def get_organization_orbits(
    request: Request, organization_id: int
) -> list[Orbit]:
    return await orbit_handler.get_organization_orbits(request.user.id, organization_id)


@organization_orbits_router.post("", responses=endpoint_responses, response_model=Orbit)
async def create_orbit(
    request: Request, organization_id: int, orbit: OrbitCreateIn
) -> Orbit:
    return await orbit_handler.create_organization_orbit(
        request.user.id, organization_id, orbit
    )


@organization_orbits_router.get(
    "/{orbit_id}", responses=endpoint_responses, response_model=OrbitDetails
)
async def get_orbit_details(
    request: Request, organization_id: int, orbit_id: int
) -> OrbitDetails:
    return await orbit_handler.get_orbit(request.user.id, organization_id, orbit_id)


@organization_orbits_router.patch(
    "/{orbit_id}", responses=endpoint_responses, response_model=Orbit
)
async def update_orbit(
    request: Request, organization_id: int, orbit_id: int, orbit: OrbitUpdate
) -> Orbit:
    return await orbit_handler.update_orbit(
        request.user.id, organization_id, orbit_id, orbit
    )


@organization_orbits_router.delete(
    "/{orbit_id}", responses=endpoint_responses, status_code=status.HTTP_204_NO_CONTENT
)
async def delete_orbit(request: Request, organization_id: int, orbit_id: int) -> None:
    return await orbit_handler.delete_orbit(request.user.id, organization_id, orbit_id)
