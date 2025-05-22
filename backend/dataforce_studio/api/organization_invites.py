from fastapi import APIRouter, status

from dataforce_studio.handlers.organizations import OrganizationHandler
from dataforce_studio.schemas.organization import (
    CreateOrganizationInvite,
    OrganizationInvite,
)

invites_router = APIRouter(
    prefix="/{organization_id}/invitations", tags=["organization-invites"]
)

organization_handler = OrganizationHandler()


@invites_router.get("", response_model=list[OrganizationInvite])
async def get_organization_invites(organization_id: int) -> list[OrganizationInvite]:
    return await organization_handler.get_organization_invites(organization_id)


@invites_router.post("", response_model=OrganizationInvite)
async def create_invite_in_organization(
    invite: CreateOrganizationInvite,
) -> OrganizationInvite:
    return await organization_handler.send_invite(invite)


@invites_router.delete("/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_invite_to_organization(invite_id: int) -> None:
    return await organization_handler.cancel_invite(invite_id)
