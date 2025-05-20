import uuid

from dataforce_studio.infra.db import engine
from dataforce_studio.infra.exceptions import (
    NotFoundError,
    OrbitLimitReachedError,
    OrganizationLimitReachedError,
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


class OrbitHandler:
    __orbits_repository = OrbitRepository(engine)

    __members_limit = 10
    __orbits_limit = 10

    async def check_organization_orbits_limit(
        self, organization_id: uuid.UUID, num: int = 0
    ) -> None:
        orbits_count = await self.__orbits_repository.get_organization_orbits_count(
            organization_id
        )

        if (orbits_count + num) >= self.__orbits_limit:
            raise OrganizationLimitReachedError(
                "Organization reached maximum number of orbits", 409
            )

    async def check_organization_members_limit(
        self, organization_id: uuid.UUID, num: int = 0
    ) -> None:
        members_count = await self.__orbits_repository.get_orbit_members_count(
            organization_id
        )

        if (members_count + num) >= self.__orbits_limit:
            raise OrbitLimitReachedError("Orbit reached maximum number of members", 409)

    async def create_organization_orbit(self, orbit: OrbitCreate) -> Orbit:
        await self.check_organization_orbits_limit(orbit.organization_id)

        return await self.__orbits_repository.create_orbit(orbit)

    async def get_organization_orbits(self, organization_id: uuid.UUID) -> list[Orbit]:
        return await self.__orbits_repository.get_organization_orbits(organization_id)

    async def get_orbit(self, orbit_id: uuid.UUID) -> OrbitDetails:
        orbit = await self.__orbits_repository.get_orbit(orbit_id)

        if not orbit:
            raise NotFoundError("Orbit not found")

        return orbit

    async def update_orbit(self, orbit: OrbitUpdate) -> Orbit:
        orbit_obj = await self.__orbits_repository.update_orbit(orbit)

        if not orbit_obj:
            raise NotFoundError("Orbit not found")

        return orbit_obj

    async def delete_orbit(self, orbit_id: uuid.UUID) -> None:
        return await self.__orbits_repository.delete_orbit(orbit_id)

    async def get_orbit_members(self, orbit_id: uuid.UUID) -> list[OrbitMember]:
        return await self.__orbits_repository.get_orbit_members(orbit_id)

    async def create_orbit_member(self, member: OrbitMemberCreate) -> OrbitMember:
        await self.check_organization_members_limit(member.orbit_id)

        return await self.__orbits_repository.create_orbit_member(member)

    async def update_orbit_member(self, member: UpdateOrbitMember) -> OrbitMember:
        member_obj = await self.__orbits_repository.update_orbit_member(member)

        if not member_obj:
            raise NotFoundError("Orbit Member not found")

        return member_obj

    async def delete_orbit_member(self, member_id: uuid.UUID) -> None:
        return await self.__orbits_repository.delete_orbit_member(member_id)
