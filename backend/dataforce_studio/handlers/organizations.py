import uuid

from pydantic import EmailStr

from dataforce_studio.handlers.emails import EmailHandler
from dataforce_studio.infra.db import engine
from dataforce_studio.infra.exceptions import (
    NotFoundError,
    OrganizationLimitReachedError,
)
from dataforce_studio.models.organization import OrganizationInviteOrm
from dataforce_studio.repositories.invites import InviteRepository
from dataforce_studio.repositories.users import UserRepository
from dataforce_studio.schemas.organization import (
    CreateOrganizationInvite,
    OrganizationDetails,
    OrganizationInvite,
    OrganizationMember,
    OrganizationMemberCreate,
    OrganizationSwitcher,
    UpdateOrganizationMember,
)


class OrganizationHandler:
    __invites_repository = InviteRepository(engine)
    __email_handler = EmailHandler()
    __user_repository = UserRepository(engine)

    __members_limit = 10

    async def get_user_organizations(
        self, user_id: uuid.UUID
    ) -> list[OrganizationSwitcher]:
        return await self.__user_repository.get_user_organizations(user_id)

    async def get_organization(self, organization_id: uuid.UUID) -> OrganizationDetails:
        organization = await self.__user_repository.get_organization_details(
            organization_id
        )
        if not organization:
            raise NotFoundError("Organization not found")
        return organization

    async def check_org_members_limit(
        self, organization_id: uuid.UUID, num: int = 0
    ) -> None:
        members_count = await self.__user_repository.get_organization_members_count(
            organization_id
        )

        if (members_count + num) >= self.__members_limit:
            raise OrganizationLimitReachedError(
                "Organization reached maximum number of users", 409
            )

    async def send_invite(self, invite: CreateOrganizationInvite) -> OrganizationInvite:
        await self.check_org_members_limit(invite.organization_id)

        db_invite = await self.__invites_repository.create_organization_invite(
            OrganizationInviteOrm(**invite.model_dump())
        )
        # TODO implement invite sending email
        self.__email_handler.send_organization_invite_email()
        return db_invite

    async def cancel_invite(self, invite_id: uuid.UUID) -> None:
        return await self.__invites_repository.delete_organization_invite(invite_id)

    async def accept_invite(self, invite_id: uuid.UUID, user_id: uuid.UUID) -> None:
        invite = await self.__invites_repository.get_invite(invite_id)

        await self.check_org_members_limit(invite.organization_id, 1)
        await self.__user_repository.create_organization_member(
            user_id, invite.organization_id, invite.role
        )
        await self.__invites_repository.delete_organization_invites_for_user(
            invite.organization_id, invite.email
        )

    async def reject_invite(self, invite_id: uuid.UUID) -> None:
        return await self.__invites_repository.delete_organization_invite(invite_id)

    async def get_organization_invites(
        self, organization_id: uuid.UUID
    ) -> list[OrganizationInvite]:
        return await self.__invites_repository.get_invites_by_organization_id(
            organization_id
        )

    async def get_user_invites(self, email: EmailStr) -> list[OrganizationInvite]:
        return await self.__invites_repository.get_invites_by_user_email(email)

    async def get_organization_members_data(
        self, organization_id: uuid.UUID
    ) -> list[OrganizationMember]:
        return await self.__user_repository.get_organization_members(organization_id)

    async def update_organization_member_by_id(
        self, member: UpdateOrganizationMember
    ) -> OrganizationMember | None:
        return await self.__user_repository.update_organization_member(member)

    async def delete_organization_member_by_id(self, member_id: uuid.UUID) -> None:
        return await self.__user_repository.delete_organization_member(member_id)

    async def add_organization_member(
        self, member: OrganizationMemberCreate
    ) -> OrganizationMember:
        return await self.__user_repository.create_organization_member(
            member.user_id, member.organization_id, member.role
        )
