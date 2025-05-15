import uuid

from fastapi import APIRouter, HTTPException, Request, status
from starlette.authentication import UnauthenticatedUser

from dataforce_studio.api.auth import handle_auth_error
from dataforce_studio.handlers.organizations import OrganizationHandler
from dataforce_studio.models.errors import AuthError
from dataforce_studio.schemas.invite import OrganizationInvite

user_invites_router = APIRouter(prefix="/organization")

organization_handler = OrganizationHandler()


@user_invites_router.get("/me/invitations", response_model=list[OrganizationInvite])
async def get_user_invites(request: Request) -> list[OrganizationInvite]:
    return await organization_handler.get_user_invites(request.user.email)


@user_invites_router.post("/me/invitations/{invite_id}/accept")
async def accept_invite_to_organization(request: Request, invite_id: uuid.UUID) -> None:
    if isinstance(request.user, UnauthenticatedUser):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    try:
        return await organization_handler.accept_invite(invite_id, request.user.id)
    except AuthError as e:
        raise handle_auth_error(e) from e


@user_invites_router.post(
    "/me/invitations/{invite_id}/reject", status_code=status.HTTP_204_NO_CONTENT
)
async def reject_invite_to_organization(invite_id: uuid.UUID) -> None:
    return await organization_handler.reject_invite(invite_id)
