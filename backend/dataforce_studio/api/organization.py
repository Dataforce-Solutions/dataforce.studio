from fastapi import APIRouter, Request

from dataforce_studio.handlers.organizations import OrganizationHandler
from dataforce_studio.schemas.organization import (
    OrganizationDetails,
    OrganizationSwitcher,
)

organization_router = APIRouter(prefix="", tags=["organizations"])

organization_handler = OrganizationHandler()


@organization_router.get("/all", response_model=list[OrganizationSwitcher])
async def get_available_organizations(request: Request) -> list[OrganizationSwitcher]:
    return await organization_handler.get_user_organizations(request.user.id)


@organization_router.get("/{organization_id}", response_model=OrganizationDetails)
async def get_organization_details(organization_id: int) -> OrganizationDetails:
    return await organization_handler.get_organization(organization_id)
