import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from ..handlers.organizations import OrganizationHandler
from ..infra.dependencies import get_current_user
from ..models.auth import AuthUser
from ..schemas.organization import OrganizationDetails, OrganizationSwitcher

organization_router = APIRouter(prefix="/organizations", tags=["organizations"])

organization_handler = OrganizationHandler()


@organization_router.get("", response_model=list[OrganizationSwitcher])
async def get_available_organizations(
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> list[OrganizationSwitcher]:
    return await organization_handler.get_user_organizations(user.id)


@organization_router.get("/{organization_id}", response_model=OrganizationDetails)
async def get_organization_details(
    organization_id: uuid.UUID, _: Annotated[AuthUser, Depends(get_current_user)]
) -> OrganizationDetails:
    return await organization_handler.get_organization(organization_id)
