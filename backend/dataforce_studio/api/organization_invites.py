import uuid

from fastapi import APIRouter, Depends, Request, status

from dataforce_studio.handlers.organizations import OrganizationHandler
from dataforce_studio.infra.dependencies import is_user_authenticated
from dataforce_studio.schemas.invite import (
    CreateOrganizationInvite,
    OrganizationInvite,
)

invites_router = APIRouter(
    prefix="/invites",
    tags=["organization-invites"],
    dependencies=[Depends(is_user_authenticated)],
)

organization_handler = OrganizationHandler()


@invites_router.get("/{organization_id}", response_model=list[OrganizationInvite])
async def get_organization_invites(
    organization_id: uuid.UUID,
) -> list[OrganizationInvite]:
    return await organization_handler.get_organization_invites(organization_id)


@invites_router.get("/my", response_model=list[OrganizationInvite])
async def get_user_invites(
    request: Request,
) -> list[OrganizationInvite]:
    return await organization_handler.get_user_invites(request.user.email)


@invites_router.post("", response_model=OrganizationInvite)
async def create_invite_in_organization(
    invite: CreateOrganizationInvite,
) -> OrganizationInvite:
    return await organization_handler.send_invite(invite)


@invites_router.delete("/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_invite_to_organization(
    invite_id: uuid.UUID,
) -> None:
    return await organization_handler.cancel_invite(invite_id)


@invites_router.post("/{invite_id}/accept")
async def accept_invite_to_organization(
    request: Request,
    invite_id: uuid.UUID,
) -> None:
    return await organization_handler.accept_invite(invite_id, request.user.id)


@invites_router.post("/{invite_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
async def reject_invite_to_organization(invite_id: uuid.UUID) -> None:
    return await organization_handler.reject_invite(invite_id)
