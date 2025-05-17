import uuid

from fastapi import APIRouter, Depends, Request, status

from dataforce_studio.handlers.organizations import OrganizationHandler
from dataforce_studio.infra.dependencies import is_user_authenticated
from dataforce_studio.schemas.organization import OrganizationInvite

user_invites_router = APIRouter(
    prefix="/organization",
    tags=["user-invites"],
    dependencies=[Depends(is_user_authenticated)],
)

organization_handler = OrganizationHandler()


@user_invites_router.get("/me/invitations", response_model=list[OrganizationInvite])
async def get_user_invites(request: Request) -> list[OrganizationInvite]:
    return await organization_handler.get_user_invites(request.user.email)


@user_invites_router.post("/me/invitations/{invite_id}/accept")
async def accept_invite_to_organization(request: Request, invite_id: uuid.UUID) -> None:
    return await organization_handler.accept_invite(invite_id, request.user.id)


@user_invites_router.post(
    "/me/invitations/{invite_id}/reject", status_code=status.HTTP_204_NO_CONTENT
)
async def reject_invite_to_organization(invite_id: uuid.UUID) -> None:
    return await organization_handler.reject_invite(invite_id)
