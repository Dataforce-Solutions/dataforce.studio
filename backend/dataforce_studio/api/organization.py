import uuid

from fastapi import APIRouter, Depends, Request

from dataforce_studio.handlers.organizations import OrganizationHandler
from dataforce_studio.infra.dependencies import is_user_authenticated
from dataforce_studio.schemas.organization import (
    OrganizationDetails,
    OrganizationSwitcher,
)

organization_router = APIRouter(
    prefix="/organizations",
    tags=["organizations"],
    dependencies=[Depends(is_user_authenticated)],
)

organization_handler = OrganizationHandler()


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
