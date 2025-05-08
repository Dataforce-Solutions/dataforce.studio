import uuid
from typing import Annotated

from fastapi import APIRouter, Request, status
from fastapi import APIRouter, HTTPException, Request, status
from starlette.authentication import UnauthenticatedUser
from fastapi import APIRouter, Depends, status

from dataforce_studio.handlers.organizations import OrganizationHandler
from dataforce_studio.infra.dependencies import get_current_user
from dataforce_studio.models.auth import AuthUser
from dataforce_studio.models.invite import (
    CreateOrganizationInvite,
    OrganizationInvite,
)

organization_router = APIRouter(prefix="/organization")

organization_handler = OrganizationHandler()


@organization_router.get("/invitations", response_model=list[OrganizationInvite])
async def get_organization_invites(
        organization_id: uuid.UUID, user: Annotated[AuthUser, Depends(get_current_user)]
) -> list[OrganizationInvite]:
    return await organization_handler.get_organization_invites(organization_id)


@organization_router.get("/invitations/my", response_model=list[OrganizationInvite])
async def get_user_invites(
        user: Annotated[AuthUser, Depends(get_current_user)]
) -> list[OrganizationInvite]:
    return await organization_handler.get_user_invites(user.email)


@organization_router.post("/invite", response_model=OrganizationInvite)
async def invite_to_organization(
        invite: CreateOrganizationInvite,
        user: Annotated[AuthUser, Depends(get_current_user)]
) -> OrganizationInvite:
    return await organization_handler.send_invite(invite)


@organization_router.delete("/invitations/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_invite_to_organization(invite_id: uuid.UUID, user: Annotated[AuthUser, Depends(get_current_user)) -> None:
    return await organization_handler.cancel_invite(invite_id)



@organization_router.post("/invite/accept")
async def accept_invite_to_organization(
        invite_id: uuid.UUID,
        user: Annotated[AuthUser, Depends(get_current_user)]
) -> None:

    if isinstance(user, UnauthenticatedUser):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    try:
        return await organization_handler.accept_invite(invite_id, user.id)
    except AuthError as e:
        raise handle_auth_error(e) from e
    return await organization_handler.accept_invite(invite_id, user.id)


@organization_router.post("/invite/reject", status_code=status.HTTP_204_NO_CONTENT)
async def reject_invite_to_organization(invite_id: uuid.UUID,
        user: Annotated[AuthUser, Depends(get_current_user)]) -> None:
    return await organization_handler.reject_invite(invite_id)
