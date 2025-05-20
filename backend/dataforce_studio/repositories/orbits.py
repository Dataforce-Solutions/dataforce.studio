from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from dataforce_studio.models import OrbitMembersOrm, OrbitOrm
from dataforce_studio.repositories.base import CrudMixin, RepositoryBase
from dataforce_studio.schemas.orbit import (
    Orbit,
    OrbitCreate,
    OrbitDetails,
    OrbitMember,
    OrbitMemberCreate,
    OrbitUpdate,
    UpdateOrbitMember,
)


class OrbitRepository(RepositoryBase, CrudMixin):
    # async def check_orbits_limit(self):
    #     pass

    async def get_organization_orbits(self, organization_id: int) -> list[Orbit]:
        async with self._get_session() as session:
            result = await session.execute(
                select(OrbitOrm).where(OrbitOrm.organization_id == organization_id)
            )
            db_orbits = result.scalars().all()

            return [orbit.to_orbit() for orbit in db_orbits]

    async def get_orbit(self, orbit_id: int) -> OrbitDetails | None:
        async with self._get_session() as session, session.begin():
            result = await session.execute(
                select(OrbitOrm)
                .where(OrbitOrm.id == orbit_id)
                .options(
                    selectinload(OrbitOrm.members).selectinload(OrbitMembersOrm.user)
                )
            )
            db_orbit = result.scalar_one_or_none()

            return db_orbit.to_orbit_details() if db_orbit else None

    async def get_orbit_simple(self, orbit_id: int) -> Orbit | None:
        async with self._get_session() as session, session.begin():
            result = await session.execute(
                select(OrbitOrm).where(OrbitOrm.id == orbit_id)
            )
            db_orbit = result.scalar_one_or_none()

            return db_orbit.to_orbit() if db_orbit else None

    async def create_orbit(self, orbit: OrbitCreate) -> Orbit:
        async with self._get_session() as session:
            db_orbit = await self.create_model(session, OrbitOrm, orbit)
            return db_orbit.to_orbit()

    async def update_orbit(self, orbit: OrbitUpdate) -> Orbit | None:
        async with self._get_session() as session:
            db_orbit = await self.update_model(
                session=session, orm_class=OrbitOrm, data=orbit
            )
            return db_orbit.to_orbit() if db_orbit else None

    async def delete_orbit(self, orbit_id: int) -> None:
        async with self._get_session() as session:
            return await self.delete_model(session, OrbitOrm, orbit_id)

    async def get_orbit_members(self, orbit_id: int) -> list[OrbitMember]:
        async with self._get_session() as session:
            query = select(OrbitMembersOrm).filter(OrbitMembersOrm.orbit_id == orbit_id)
            result = await session.execute(query)
            db_organization_members = result.scalars().all()
            return [member.to_orbit_member() for member in db_organization_members]

    async def create_orbit_member(self, member: OrbitMemberCreate) -> OrbitMember:
        async with self._get_session() as session:
            db_member = await self.create_model(session, OrbitMembersOrm, member)
            return db_member.to_orbit_member()

    async def update_orbit_member(
        self, member: UpdateOrbitMember
    ) -> OrbitMember | None:
        async with self._get_session() as session:
            db_member = await self.update_model(
                session=session, orm_class=OrbitMembersOrm, data=member
            )
            return db_member.to_orbit_member() if db_member else None

    async def delete_orbit_member(self, member_id: int) -> None:
        async with self._get_session() as session:
            return await self.delete_model(session, OrbitMembersOrm, member_id)

    async def get_organization_orbits_count(self, organization_id: int) -> int:
        async with self._get_session() as session:
            result = await session.execute(
                select(func.count())
                .select_from(OrbitOrm)
                .where(OrbitOrm.organization_id == organization_id)
            )
        return result.scalar() or 0

    async def get_orbit_members_count(self, orbit_id: int) -> int:
        async with self._get_session() as session:
            result = await session.execute(
                select(func.count())
                .select_from(OrbitMembersOrm)
                .where(OrbitMembersOrm.orbit_id == orbit_id)
            )
        return result.scalar() or 0
