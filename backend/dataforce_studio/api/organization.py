import uuid

from fastapi import APIRouter, Request, status
from fastapi import APIRouter, HTTPException, Request, status
from starlette.authentication import UnauthenticatedUser

from dataforce_studio.api.auth import handle_auth_error
from dataforce_studio.handlers.organizations import OrganizationHandler
from dataforce_studio.models.errors import AuthError
from dataforce_studio.models.invite import (
    CreateOrganizationInvite,
    OrganizationInvite,
)
from dataforce_studio.models.organization import DBOrganizationInvite

organization_router = APIRouter(prefix="/organization")

organization_handler = OrganizationHandler()


@organization_router.get("/invitations", response_model=list[OrganizationInvite])
async def get_organization_invites(
    request: Request, organization_id: uuid.UUID
) -> list[OrganizationInvite]:
    return await organization_handler.get_organization_invites(organization_id)


@organization_router.post("/invitations", response_model=OrganizationInvite)
@organization_router.get("/invites/my", response_model=list[OrganizationInvite])
async def get_user_invites(request: Request) -> list[OrganizationInvite]:
    return await organization_handler.get_user_invites(request.user.email)


@organization_router.post("/invite", response_model=OrganizationInvite)
async def invite_to_organization(
    request: Request, invite: CreateOrganizationInvite
) -> OrganizationInvite:
    return await organization_handler.send_invite(invite)


@organization_router.delete(
    "/invitations/{invite_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def cancel_invite_to_organization(request: Request, invite_id: uuid.UUID) -> None:
    return await organization_handler.cancel_invite(invite_id)
@organization_router.delete("/invite", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_invite_to_organization(request: Request, invite_id: uuid.UUID) -> None:
    return await organization_handler.cancel_invite(invite_id)


@organization_router.post("/invite/accept")
async def accept_invite_to_organization(request: Request, invite_id: uuid.UUID) -> None:
    if isinstance(request.user, UnauthenticatedUser):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    try:
        return await organization_handler.accept_invite(invite_id, request.user.id)
    except AuthError as e:
        raise handle_auth_error(e) from e


@organization_router.post("/invite/reject", status_code=status.HTTP_204_NO_CONTENT)
async def reject_invite_to_organization(invite_id: uuid.UUID) -> None:
    return await organization_handler.reject_invite(invite_id)
