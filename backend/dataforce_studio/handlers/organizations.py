from pydantic import EmailStr
from sqlalchemy.exc import IntegrityError

from dataforce_studio.handlers.emails import EmailHandler
from dataforce_studio.handlers.permissions import PermissionsHandler
from dataforce_studio.infra.db import engine
from dataforce_studio.infra.exceptions import (
    DatabaseConstraintError,
    NotFoundError,
    OrganizationDeleteError,
    OrganizationLimitReachedError,
    ServiceError,
)
from dataforce_studio.repositories.invites import InviteRepository
from dataforce_studio.repositories.users import UserRepository
from dataforce_studio.schemas.organization import (
    CreateOrganizationInvite,
    CreateOrganizationInviteIn,
    Organization,
    OrganizationCreateIn,
    OrganizationDetails,
    OrganizationInvite,
    OrganizationMember,
    OrganizationMemberCreate,
    OrganizationSwitcher,
    OrganizationUpdate,
    OrgRole,
    UpdateOrganizationMember,
    UserInvite,
)
from dataforce_studio.schemas.permissions import Action, Resource
from dataforce_studio.settings import config
from dataforce_studio.utils.organizations import (
    get_invited_by_name,
    get_organization_email_name,
)


class OrganizationHandler:
    __invites_repository = InviteRepository(engine)
    __email_handler = EmailHandler()
    __user_repository = UserRepository(engine)
    __permissions_handler = PermissionsHandler()

    __members_limit = 50

    async def create_organization(
        self, user_id: int, organization: OrganizationCreateIn
    ) -> Organization:
        db_org = await self.__user_repository.create_organization(user_id, organization)
        return db_org.to_organization()

    async def update_organization(
        self,
        user_id: int,
        organization_id: int,
        organization: OrganizationUpdate,
    ) -> OrganizationDetails:
        await self.__permissions_handler.check_organization_permission(
            organization_id,
            user_id,
            Resource.ORGANIZATION,
            Action.UPDATE,
        )

        org_obj = await self.__user_repository.update_organization(
            organization_id, organization
        )

        if not org_obj:
            raise NotFoundError("Organization not found")

        organization_details = await self.__user_repository.get_organization_details(
            organization_id
        )

        if not organization_details:
            raise NotFoundError("Organization not found")

        return organization_details

    async def delete_organization(self, user_id: int, organization_id: int) -> None:
        await self.__permissions_handler.check_organization_permission(
            organization_id,
            user_id,
            Resource.ORGANIZATION,
            Action.DELETE,
        )
        organization = await self.__user_repository.get_organization_details(
            organization_id
        )

        if not organization:
            raise NotFoundError("Organization not found")

        if len(organization.members) > 1:
            raise OrganizationDeleteError(
                "Organization has members and cant be deleted"
            )

        return await self.__user_repository.delete_organization(organization_id)

    async def leave_from_organization(self, user_id: int, organization_id: int) -> None:
        await self.__permissions_handler.check_organization_permission(
            organization_id,
            user_id,
            Resource.ORGANIZATION,
            Action.LEAVE,
        )

        return await self.__user_repository.delete_organization_member_by_user_id(
            user_id, organization_id
        )

    async def get_user_organizations(self, user_id: int) -> list[OrganizationSwitcher]:
        return await self.__user_repository.get_user_organizations(user_id)

    async def get_organization(
        self, user_id: int, organization_id: int
    ) -> OrganizationDetails:
        await self.__permissions_handler.check_organization_permission(
            organization_id, user_id, Resource.ORGANIZATION, Action.READ
        )

        organization = await self.__user_repository.get_organization_details(
            organization_id
        )
        if not organization:
            raise NotFoundError("Organization not found")

        return organization

    async def check_org_members_limit(self, organization_id: int) -> None:
        members_count = await self.__user_repository.get_organization_members_count(
            organization_id
        )

        if members_count >= self.__members_limit:
            raise OrganizationLimitReachedError(
                "Organization reached maximum number of users", 409
            )

    async def send_invite(
        self, user_id: int, invite_: CreateOrganizationInviteIn
    ) -> OrganizationInvite:
        await self.__permissions_handler.check_organization_permission(
            invite_.organization_id,
            user_id,
            Resource.ORGANIZATION_INVITE,
            Action.CREATE,
        )

        user_info = await self.__user_repository.get_public_user_by_id(user_id)

        if user_info and invite_.email == user_info.email:
            raise ServiceError("You can't invite yourself")

        member = await self.__user_repository.get_organization_member_by_email(
            invite_.organization_id, invite_.email
        )

        if member:
            raise ServiceError("Already a member of the organization")

        existing_invite = (
            await self.__invites_repository.get_organization_invite_by_email(
                invite_.organization_id, invite_.email
            )
        )

        if existing_invite:
            raise ServiceError("Invite already exist for this email")

        await self.check_org_members_limit(invite_.organization_id)

        db_created_invite = await self.__invites_repository.create_organization_invite(
            CreateOrganizationInvite(**invite_.model_dump(), invited_by=user_id)
        )
        invite = await self.__invites_repository.get_invite(db_created_invite.id)

        if not invite:
            raise ServiceError("Cant select created invite")

        self.__email_handler.send_organization_invite_email(
            invite.email if invite else "",
            get_invited_by_name(invite),
            get_organization_email_name(invite),
            config.APP_EMAIL_URL,
        )

        return invite

    async def cancel_invite(
        self, user_id: int, organization_id: int, invite_id: int
    ) -> None:
        await self.__permissions_handler.check_organization_permission(
            organization_id,
            user_id,
            Resource.ORGANIZATION_INVITE,
            Action.DELETE,
        )

        return await self.__invites_repository.delete_organization_invite(invite_id)

    async def accept_invite(self, invite_id: int, user_id: int) -> None:
        invite = await self.__invites_repository.get_invite(invite_id)

        if not invite:
            raise NotFoundError("Invite not found")

        await self.check_org_members_limit(invite.organization_id)

        try:
            await self.__user_repository.create_organization_member(
                OrganizationMemberCreate(
                    user_id=user_id,
                    organization_id=invite.organization_id,
                    role=invite.role,
                )
            )
        except IntegrityError as error:
            raise DatabaseConstraintError(
                "Organization member already exist."
            ) from error

        await self.__invites_repository.delete_organization_invites_for_user(
            invite.organization_id, invite.email
        )

    async def reject_invite(self, invite_id: int) -> None:
        return await self.__invites_repository.delete_organization_invite(invite_id)

    async def get_organization_invites(
        self, user_id: int, organization_id: int
    ) -> list[OrganizationInvite]:
        await self.__permissions_handler.check_organization_permission(
            organization_id,
            user_id,
            Resource.ORGANIZATION_INVITE,
            Action.LIST,
        )

        return await self.__invites_repository.get_invites_by_organization_id(
            organization_id
        )

    async def get_user_invites(self, email: EmailStr) -> list[UserInvite]:
        return await self.__invites_repository.get_invites_by_user_email(email)

    async def get_organization_members_data(
        self, user_id: int, organization_id: int
    ) -> list[OrganizationMember]:
        await self.__permissions_handler.check_organization_permission(
            organization_id,
            user_id,
            Resource.ORGANIZATION_USER,
            Action.LIST,
        )

        return await self.__user_repository.get_organization_members(organization_id)

    async def update_organization_member_by_id(
        self,
        user_id: int,
        organization_id: int,
        member_id: int,
        member: UpdateOrganizationMember,
    ) -> OrganizationMember | None:
        user_role = await self.__permissions_handler.check_organization_permission(
            organization_id,
            user_id,
            Resource.ORGANIZATION_USER,
            Action.CREATE,
        )

        member_to_update = await self.__user_repository.get_organization_member_by_id(
            member_id
        )

        if not member_to_update:
            raise ServiceError("Member does not exist.")

        if user_id == member_to_update.user.id:
            raise ServiceError("You can not update your own data.")

        if user_role != OrgRole.OWNER and member.role == OrgRole.ADMIN:
            raise ServiceError("Only Organization Owner can assign new admins.")

        return await self.__user_repository.update_organization_member(
            member_id, member
        )

    async def delete_organization_member_by_id(
        self, user_id: int, organization_id: int, member_id: int
    ) -> None:
        await self.__permissions_handler.check_organization_permission(
            organization_id,
            user_id,
            Resource.ORGANIZATION_USER,
            Action.DELETE,
        )

        member_to_delete = await self.__user_repository.get_organization_member_by_id(
            member_id
        )

        if not member_to_delete:
            raise ServiceError("Member does not exist.")

        if user_id == member_to_delete.user.id:
            raise ServiceError("You can not remove yourself from organization.")

        if member_to_delete and member_to_delete.role == OrgRole.OWNER:
            raise ServiceError("Organization Owner can not be removed.")

        return await self.__user_repository.delete_organization_member(member_id)

    async def add_organization_member(
        self, user_id: int, organization_id: int, member: OrganizationMemberCreate
    ) -> OrganizationMember:
        user_role = await self.__permissions_handler.check_organization_permission(
            organization_id,
            user_id,
            Resource.ORGANIZATION_USER,
            Action.CREATE,
        )

        if user_role != OrgRole.OWNER and member.role == OrgRole.ADMIN:
            raise ServiceError("Only Organization Owner can add new admins.")
        try:
            created_member = await self.__user_repository.create_organization_member(
                member
            )
        except IntegrityError as error:
            raise DatabaseConstraintError(
                "Organization member already exist."
            ) from error

        return created_member
