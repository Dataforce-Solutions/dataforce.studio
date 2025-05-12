import uuid

from fastapi import APIRouter, Request, status

from dataforce_studio.handlers.organizations import OrganizationHandler
from dataforce_studio.models.invite import (
    CreateOrganizationInvite,
    OrganizationInvite,
)

organization_router = APIRouter(prefix="/organization")

organization_handler = OrganizationHandler()


@organization_router.get("/invitations", response_model=list[OrganizationInvite])
async def get_organization_invites(
    request: Request, organization_id: uuid.UUID
) -> list[OrganizationInvite]:
    return await organization_handler.get_organization_invites(organization_id)


@organization_router.post("/invitations", response_model=OrganizationInvite)
async def invite_to_organization(
    request: Request, invite: CreateOrganizationInvite
) -> OrganizationInvite:
    return await organization_handler.send_invite(invite)


@organization_router.delete(
    "/invitations/{invite_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def cancel_invite_to_organization(request: Request, invite_id: uuid.UUID) -> None:
    return await organization_handler.cancel_invite(invite_id)
