import uuid

from dataforce_studio.handlers.emails import EmailHandler
from dataforce_studio.infra.db import engine
from dataforce_studio.models.invite import CreateOrganizationInvite, OrganizationInvite
from dataforce_studio.models.organization import DBOrganizationInvite
from dataforce_studio.repositories.invites import InviteRepository
from dataforce_studio.repositories.users import UserRepository


class OrganizationHandler:
    __invites_repository = InviteRepository(engine)
    __email_handler = EmailHandler()
    __user_repository = UserRepository(engine)

    __members_limit = 10

    async def check_org_members_limit(
        self, organization_id: uuid.UUID, num: int = 0
    ) -> None:
        members_count = await self.__user_repository.get_organization_members_count(
            organization_id
        )
        members_count = members_count or 0

        if (members_count + num) >= self.__members_limit:
            raise ValueError("Organization reached maximum number of users")

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

    async def cancel_invite(self, invite_id: uuid.UUID) -> None:
        """Handle canceling invite to organization"""

        return await self.__invites_repository.delete_organization_invite(invite_id)

    async def accept_invite(self, invite_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Handle accepting invite to organization"""

        invite = await self.__invites_repository.get_invite(invite_id)

        await self.check_org_members_limit(invite.organization_id, 1)
        await self.__user_repository.create_organization_member(
            user_id, invite.organization_id, invite.role
        )
        await self.__invites_repository.delete_organization_invites_where(
            DBOrganizationInvite.organization_id == invite.organization_id,
            DBOrganizationInvite.email == invite.email,
        )

    async def reject_invite(self, invite_id: uuid.UUID) -> None:
        """Handle rejecting invite to organization"""

        return await self.__invites_repository.delete_organization_invite(invite_id)

    async def get_organization_invites(
        self, organization_id: uuid.UUID
    ) -> list[OrganizationInvite]:
        """Handle listing all organization's invite"""

        return await self.__invites_repository.get_invites_where(
            DBOrganizationInvite.organization_id == organization_id
        )

    async def get_user_invites(self, email: str) -> list[OrganizationInvite]:
        """Handle listing all invites sent to user"""

        return await self.__invites_repository.get_invites_where(
            DBOrganizationInvite.email == email
        )
