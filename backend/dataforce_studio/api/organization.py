import uuid

from fastapi import APIRouter, Depends, Request

from dataforce_studio.handlers.organizations import OrganizationHandler
from dataforce_studio.infra.dependencies import is_user_authenticated
from dataforce_studio.schemas.organization import (
    OrganizationDetails,
    OrganizationSwitcher,
)

from .orbits import orbits_router, organization_orbits_router
from .orbits_members import orbit_members_router, orbit_router
from .organization_invites import invites_router
from .organization_members import members_router

organization_router = APIRouter(
    prefix="/organizations",
    tags=["organizations"],
    dependencies=[Depends(is_user_authenticated)],
)

organization_handler = OrganizationHandler()


organization_router.include_router(invites_router)
organization_router.include_router(members_router)
organization_router.include_router(organization_orbits_router)
organization_router.include_router(orbits_router)
organization_router.include_router(orbit_router)
organization_router.include_router(orbit_members_router)


@organization_router.get("", response_model=list[OrganizationSwitcher])
async def get_available_organizations(
    request: Request,
) -> list[OrganizationSwitcher]:
    return await organization_handler.get_user_organizations(request.user.id)


@organization_router.get("/{organization_id}", response_model=OrganizationDetails)
async def get_organization_details(
    organization_id: uuid.UUID,
) -> OrganizationDetails:
    return await organization_handler.get_organization(organization_id)
