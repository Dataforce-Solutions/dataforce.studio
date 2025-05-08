import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from dataforce_studio.handlers.organizations import OrganizationHandler
from dataforce_studio.infra.dependencies import get_current_user
from dataforce_studio.models.auth import AuthUser

members_router = APIRouter(prefix="/members", tags=["organization-members"])

organization_handler = OrganizationHandler()


@members_router.get("/{organization_id}")
async def get_organization_members(
        organization_id: uuid.UUID,
        user: Annotated[AuthUser, Depends(get_current_user)]
):
    pass
