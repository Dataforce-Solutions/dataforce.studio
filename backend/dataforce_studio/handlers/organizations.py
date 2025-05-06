import uuid

from dataforce_studio.handlers.emails import EmailHandler
from dataforce_studio.models.invite import CreateOrganizationInvite, OrganizationInvite
from dataforce_studio.models.organization import DBOrganizationInvite
from dataforce_studio.repositories.invites import InviteRepository
from dataforce_studio.repositories.users import UserRepository


class OrganizationHandler:
    __invites_repository = InviteRepository()
    __email_handler = EmailHandler()
    __user_repository = UserRepository()

    __members_limit = 10

    async def check_org_members_limit(self, organization_id: uuid.UUID) -> None:
        members_count = await (self.__user_repository
                               .get_organization_members_count(organization_id))

        if members_count >= self.__members_limit:
            raise ValueError('Organization reached maximum number of users')


    async def send_invite(
            self, invite: CreateOrganizationInvite
    ) -> DBOrganizationInvite:
        """Handle sending invite to organization"""

        await self.check_org_members_limit(invite.organization_id)

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

    async def get_organization_invites(
            self, organization_id: uuid.UUID
    ) -> list[OrganizationInvite]:
        return await self.__invites_repository.get_invites_where(
            DBOrganizationInvite.organization_id == organization_id
        )

    async def get_user_invites(self, email: str) -> list[OrganizationInvite]:
        return await self.__invites_repository.get_invites_where(
            DBOrganizationInvite.email == email
        )
