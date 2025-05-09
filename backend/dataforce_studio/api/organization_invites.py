import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from dataforce_studio.handlers.organizations import OrganizationHandler
from dataforce_studio.infra.dependencies import get_current_user
from dataforce_studio.models.auth import AuthUser
from dataforce_studio.schemas.invite import (
    CreateOrganizationInvite,
    OrganizationInvite,
)
from dataforce_studio.models.organization import DBOrganizationInvite

invites_router = APIRouter(prefix="/invites", tags=["organization-invites"])

organization_handler = OrganizationHandler()


@invites_router.get("/{organization_id}", response_model=list[OrganizationInvite])
async def get_organization_invites(
        organization_id: uuid.UUID, user: Annotated[AuthUser, Depends(get_current_user)]
) -> list[OrganizationInvite]:
    return await organization_handler.get_organization_invites(organization_id)


@invites_router.get("/my", response_model=list[OrganizationInvite])
async def get_user_invites(
        user: Annotated[AuthUser, Depends(get_current_user)]
) -> list[OrganizationInvite]:
    return await organization_handler.get_user_invites(user.email)


@invites_router.post("/", response_model=OrganizationInvite)
async def create_invite_in_organization(
        invite: CreateOrganizationInvite,
        user: Annotated[AuthUser, Depends(get_current_user)]
) -> DBOrganizationInvite:
    return await organization_handler.send_invite(invite)


@invites_router.delete("/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_invite_to_organization(
        invite_id: uuid.UUID,
        user: Annotated[AuthUser, Depends(get_current_user)]
) -> None:
    return await organization_handler.cancel_invite(invite_id)


@invites_router.post("/{invite_id}/accept")
async def accept_invite_to_organization(
        invite_id: uuid.UUID,
        user: Annotated[AuthUser, Depends(get_current_user)]
) -> None:
    return await organization_handler.accept_invite(invite_id, user.id)


@invites_router.post("/{invite_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
async def reject_invite_to_organization(
        invite_id: uuid.UUID,
        user: Annotated[AuthUser, Depends(get_current_user)]
) -> None:
    return await organization_handler.reject_invite(invite_id)
