from fastapi import APIRouter, Depends, Request, status

from dataforce_studio.handlers.organizations import OrganizationHandler
from dataforce_studio.infra.dependencies import is_user_authenticated
from dataforce_studio.schemas.organization import OrganizationInvite, UserInvite

user_invites_router = APIRouter(
    prefix="/me/invitations",
    dependencies=[Depends(is_user_authenticated)],
)

organization_handler = OrganizationHandler()


@user_invites_router.get("", response_model=list[UserInvite])
async def get_user_invites(request: Request) -> list[UserInvite]:
    return await organization_handler.get_user_invites(request.user.email)


@user_invites_router.post("/{invite_id}/accept")
async def accept_invite_to_organization(request: Request, invite_id: int) -> None:
    return await organization_handler.accept_invite(invite_id, request.user.id)


@user_invites_router.post("/{invite_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
async def reject_invite_to_organization(invite_id: int) -> None:
    return await organization_handler.reject_invite(invite_id)
