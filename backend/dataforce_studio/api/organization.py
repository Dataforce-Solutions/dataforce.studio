import uuid

from fastapi import APIRouter
from pydantic import EmailStr

from dataforce_studio.handlers.organizations import OrganizationHandler
from dataforce_studio.models.invite import (
    CreateOrganizationInvite,
    OrganizationInvite,
)

organization_router = APIRouter(prefix="/organization", tags=["organization"])

organization_handler = OrganizationHandler()


@organization_router.get('/invites', response_model=list[OrganizationInvite])
async def get_organization_invites(
        organization_id: uuid.UUID
) -> list[OrganizationInvite]:
    return await organization_handler.get_organization_invites(organization_id)


@organization_router.get('/invites/my', response_model=list[OrganizationInvite])
async def get_user_invites(email: EmailStr) -> list[OrganizationInvite]:
    return await organization_handler.get_user_invites(email)


@organization_router.post('/invite', response_model=OrganizationInvite)
async def invite_to_organization(
        invite: CreateOrganizationInvite
) -> OrganizationInvite:
    return await organization_handler.send_invite(invite)


@organization_router.delete('/invite', response_model=OrganizationInvite)
async def cancel_invite_to_organization() -> None:
    pass


@organization_router.post('/invite/accept', response_model=OrganizationInvite)
async def accept_invite_to_organization() -> None:
    pass


@organization_router.post('/invite/reject', response_model=OrganizationInvite)
async def reject_invite_to_organization() -> None:
    pass
