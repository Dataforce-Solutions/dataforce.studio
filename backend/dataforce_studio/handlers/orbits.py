from dataforce_studio.infra.db import engine
from dataforce_studio.infra.exceptions import (
    NotFoundError,
    OrganizationLimitReachedError,
    ServiceError,
)
from dataforce_studio.repositories.orbits import OrbitRepository
from dataforce_studio.schemas.orbit import (
    Orbit,
    OrbitCreate,
    OrbitDetails,
    OrbitMember,
    OrbitMemberCreate,
    OrbitUpdate,
    UpdateOrbitMember,
)
from dataforce_studio.schemas.permissions import Action, Resource


class OrbitHandler:
    __orbits_repository = OrbitRepository(engine)
    __permissions_handler = PermissionsHandler()

    __orbits_limit = 10

    async def check_organization_orbits_limit(self, organization_id: int) -> None:
        orbits_count = await self.__orbits_repository.get_organization_orbits_count(
            organization_id
        )

        if orbits_count >= self.__orbits_limit:
            raise OrganizationLimitReachedError(
                "Organization reached maximum number of orbits", 409
            )

    async def create_organization_orbit(
        self, user_id: int, organization_id: int, orbit: OrbitCreate
    ) -> Orbit:
        await self.__permissions_handler.check_organization_permission(
            organization_id,
            user_id,
            Resource.ORBIT,
            Action.CREATE,
        )

        await self.check_organization_orbits_limit(organization_id)

        return await self.__orbits_repository.create_orbit(organization_id, orbit)

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


        return await self.__orbits_repository.create_orbit_member(member)

    async def update_orbit_member(
        self,
        user_id: int,
        organization_id: int,
        orbit_id: int,
        member: UpdateOrbitMember,
    ) -> OrbitMember:
        if user_id == member.id:
            raise ServiceError("You can not update your own data.")

        await self.__permissions_handler.check_orbit_action_access(
            organization_id,
            orbit_id,
            user_id,
            Resource.ORBIT_USER,
            Action.UPDATE,
        )

        member_obj = await self.__orbits_repository.update_orbit_member(member)

        if not member_obj:
            raise NotFoundError("Orbit Member not found")

        return member_obj

    async def delete_orbit_member(
        self, user_id: int, organization_id: int, orbit_id: int, member_id: int
    ) -> None:

        if user_id == member_id:
            raise ServiceError("You can not remove yourself from orbit.")

        await self.__permissions_handler.check_orbit_action_access(
            organization_id,
            orbit_id,
            user_id,
            Resource.ORBIT_USER,
            Action.DELETE,
        )
        return await self.__orbits_repository.delete_orbit_member(member_id)
