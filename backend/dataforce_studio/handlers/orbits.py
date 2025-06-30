from fastapi import BackgroundTasks
from sqlalchemy.exc import IntegrityError

from dataforce_studio.handlers.emails import EmailHandler
from dataforce_studio.handlers.permissions import PermissionsHandler
from dataforce_studio.infra.db import engine
from dataforce_studio.infra.exceptions import (
    NotFoundError,
    OrganizationLimitReachedError,
    ServiceError,
)
from dataforce_studio.repositories.bucket_secrets import BucketSecretRepository
from dataforce_studio.repositories.orbits import OrbitRepository
from dataforce_studio.repositories.users import UserRepository
from dataforce_studio.schemas.orbit import (
    Orbit,
    OrbitCreateIn,
    OrbitDetails,
    OrbitMember,
    OrbitMemberCreate,
    OrbitMemberCreateSimple,
    OrbitUpdate,
    UpdateOrbitMember,
)
from dataforce_studio.schemas.permissions import Action, Resource
from dataforce_studio.settings import config


class OrbitHandler:
    __email_handler = EmailHandler()
    __user_repository = UserRepository(engine)
    __orbits_repository = OrbitRepository(engine)
    __permissions_handler = PermissionsHandler()
    __secret_repository = BucketSecretRepository(engine)

    __orbits_limit = 10

    def notify_members(
        self, orbit: OrbitDetails, background_tasks: BackgroundTasks
    ) -> None:
        if orbit.members:
            for member in orbit.members:
                background_tasks.add_task(
                    self.__email_handler.send_added_to_orbit_email,
                    member.user.full_name or "",
                    member.user.email or "",
                    orbit.name or "",
                    config.APP_EMAIL_URL,
                )

    async def _check_organization_orbits_limit(self, organization_id: int) -> None:
        orbits_count = await self.__orbits_repository.get_organization_orbits_count(
            organization_id
        )

        if orbits_count >= self.__orbits_limit:
            raise OrganizationLimitReachedError(
                "Organization reached maximum number of orbits", 409
            )

    async def _validate_orbit_members(
        self,
        user_id: int,
        organization_id: int,
        members: list[OrbitMemberCreate] | list[OrbitMemberCreateSimple],
    ) -> None:
        user_ids = [m.user_id for m in members]

        if len(user_ids) != len(set(user_ids)):
            raise ServiceError("Orbit members should contain only unique values.")

        if user_id in user_ids:
            raise ServiceError("You can not add yourself to orbit.")

        org_members = await self.__user_repository.get_organization_members_by_user_ids(
            organization_id, user_ids
        )

        invalid_user_ids = set(user_ids) - {m.user.id for m in org_members}

        if invalid_user_ids:
            raise ServiceError(f"Users {invalid_user_ids} are not in the organization.")

    async def create_organization_orbit(
        self, user_id: int, organization_id: int, orbit: OrbitCreateIn
    ) -> OrbitDetails:
        await self.__permissions_handler.check_organization_permission(
            organization_id,
            user_id,
            Resource.ORBIT,
            Action.CREATE,
        )

        await self._check_organization_orbits_limit(organization_id)
        secret = await self.__secret_repository.get_bucket_secret(
            orbit.bucket_secret_id
        )
        if not secret or secret.organization_id != organization_id:
            raise NotFoundError("Bucket secret not found")

        if orbit.members:
            await self._validate_orbit_members(user_id, organization_id, orbit.members)
        created_orbit = await self.__orbits_repository.create_orbit(
            organization_id, orbit
        )

        if not created_orbit:
            raise ServiceError("Some errors when creating")

        return created_orbit

    async def get_organization_orbits(
        self, user_id: int, organization_id: int
    ) -> list[Orbit]:
        await self.__permissions_handler.check_organization_permission(
            organization_id,
            user_id,
            Resource.ORBIT,
            Action.LIST,
        )
        return await self.__orbits_repository.get_organization_orbits(organization_id)

    async def get_orbit(
        self, user_id: int, organization_id: int, orbit_id: int
    ) -> OrbitDetails:
        await self.__permissions_handler.check_orbit_action_access(
            organization_id,
            orbit_id,
            user_id,
            Resource.ORBIT,
            Action.READ,
        )

        orbit = await self.__orbits_repository.get_orbit(orbit_id)

        if not orbit:
            raise NotFoundError("Orbit not found")

        return orbit

    async def update_orbit(
        self, user_id: int, organization_id: int, orbit_id: int, orbit: OrbitUpdate
    ) -> Orbit:
        await self.__permissions_handler.check_orbit_action_access(
            organization_id,
            orbit_id,
            user_id,
            Resource.ORBIT,
            Action.UPDATE,
        )

        orbit_obj = await self.__orbits_repository.update_orbit(orbit_id, orbit)

        if not orbit_obj:
            raise NotFoundError("Orbit not found")

        return orbit_obj

    async def delete_orbit(
        self, user_id: int, organization_id: int, orbit_id: int
    ) -> None:
        await self.__permissions_handler.check_orbit_action_access(
            organization_id,
            orbit_id,
            user_id,
            Resource.ORBIT,
            Action.DELETE,
        )

        return await self.__orbits_repository.delete_orbit(orbit_id)

    async def get_orbit_members(
        self, user_id: int, organization_id: int, orbit_id: int
    ) -> list[OrbitMember]:
        await self.__permissions_handler.check_orbit_action_access(
            organization_id,
            orbit_id,
            user_id,
            Resource.ORBIT_USER,
            Action.LIST,
        )
        return await self.__orbits_repository.get_orbit_members(orbit_id)

    async def create_orbit_member(
        self, user_id: int, organization_id: int, member: OrbitMemberCreate
    ) -> OrbitMember:
        await self.__permissions_handler.check_orbit_action_access(
            organization_id,
            member.orbit_id,
            user_id,
            Resource.ORBIT_USER,
            Action.CREATE,
        )

        org_member = await self.__user_repository.get_organization_member(
            organization_id, member.user_id
        )

        if not org_member:
            raise ServiceError(
                "User must be a member of the organization to be added to an orbit."
            )

        if user_id == member.user_id:
            raise ServiceError("You can not add yourself to orbit.")
        try:
            created_member = await self.__orbits_repository.create_orbit_member(member)
        except IntegrityError as error:
            raise ServiceError("Member already exist.") from error

        orbit = await self.__orbits_repository.get_orbit_simple(
            member.orbit_id,
        )

        self.__email_handler.send_added_to_orbit_email(
            created_member.user.full_name
            if created_member.user and created_member.user.full_name
            else "",
            created_member.user.email
            if created_member.user and created_member.user.email
            else "",
            orbit.name if orbit else "",
            config.APP_EMAIL_URL,
        )

        return created_member

    async def update_orbit_member(
        self,
        user_id: int,
        organization_id: int,
        orbit_id: int,
        member: UpdateOrbitMember,
    ) -> OrbitMember:
        member_obj = await self.__orbits_repository.get_orbit_member(member.id)

        if not member_obj:
            raise NotFoundError("Orbit Member not found")

        if user_id == member_obj.user.id:
            raise ServiceError("You can not update your own data.")

        await self.__permissions_handler.check_orbit_action_access(
            organization_id,
            orbit_id,
            user_id,
            Resource.ORBIT_USER,
            Action.UPDATE,
        )
        updated = await self.__orbits_repository.update_orbit_member(member)

        if not updated:
            raise NotFoundError("Orbit Member not found")

        return updated

    async def delete_orbit_member(
        self, user_id: int, organization_id: int, orbit_id: int, member_id: int
    ) -> None:
        member_obj = await self.__orbits_repository.get_orbit_member(member_id)

        if not member_obj:
            raise NotFoundError("Orbit Member not found")

        if user_id == member_obj.user.id:
            raise ServiceError("You can not remove yourself from orbit.")

        await self.__permissions_handler.check_orbit_action_access(
            organization_id,
            orbit_id,
            user_id,
            Resource.ORBIT_USER,
            Action.DELETE,
        )
        return await self.__orbits_repository.delete_orbit_member(member_id)
