from fastapi import APIRouter, Request

from dataforce_studio.handlers.organizations import OrganizationHandler
from dataforce_studio.schemas.organization import OrganizationSwitcher

user_router = APIRouter(prefix="", tags=["users-me"])

organization_handler = OrganizationHandler()


@user_router.get("/organizations", response_model=list[OrganizationSwitcher])
async def get_available_organizations(request: Request) -> list[OrganizationSwitcher]:
    return await organization_handler.get_user_organizations(request.user.id)
