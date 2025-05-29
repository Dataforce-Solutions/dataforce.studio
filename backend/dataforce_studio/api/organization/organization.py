from fastapi import APIRouter, Request

from dataforce_studio.handlers.organizations import OrganizationHandler
from dataforce_studio.infra.endpoint_responses import endpoint_responses
from dataforce_studio.schemas.organization import OrganizationDetails

organization_router = APIRouter(prefix="", tags=["organizations"])

organization_handler = OrganizationHandler()


@organization_router.get(
    "/{organization_id}",
    responses=endpoint_responses,
    response_model=OrganizationDetails,
)
async def get_organization_details(
    request: Request, organization_id: int
) -> OrganizationDetails:
    return await organization_handler.get_organization(request.user.id, organization_id)
