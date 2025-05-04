from dataforce_studio.handlers.emails import EmailHandler
from dataforce_studio.models.invite import CreateOrganizationInvite
from dataforce_studio.models.organization import DBOrganizationInvite
from dataforce_studio.repositories.invites import InviteRepository


class OrganizationHandler:
    __invites_repository = InviteRepository()
    __email_handler = EmailHandler()

    __members_limit = 10

    def __init__(self):
        pass

    async def send_invite(self, invite: CreateOrganizationInvite) -> DBOrganizationInvite:
        """Handle sending invite to organization"""
        db_invite = await self.__invites_repository.create_organization_invite(
            DBOrganizationInvite(**invite.model_dump())
        )
        # TODO implement invite sending email
        self.__email_handler.send_organization_invite_email()
        return db_invite

    async def cancel_invite(self) -> None:
        pass

    async def accept_invite(self) -> None:
        pass

    async def reject_invite(self) -> None:
        pass

    async def get_organization_invites(self):
        pass

    async def get_user_invites(self):
        pass

