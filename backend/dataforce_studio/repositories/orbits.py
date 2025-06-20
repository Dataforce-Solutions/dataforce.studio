from sqlalchemy import case, func, select
from sqlalchemy.orm import selectinload

from dataforce_studio.models import OrbitMembersOrm, OrbitOrm
from dataforce_studio.repositories.base import CrudMixin, RepositoryBase
from dataforce_studio.schemas.orbit import (
    Orbit,
    OrbitCreate,
    OrbitCreateIn,
    OrbitDetails,
    OrbitMember,
    OrbitMemberCreate,
    OrbitRole,
    OrbitUpdate,
    UpdateOrbitMember,
)
from dataforce_studio.utils.organizations import convert_orbit_simple_members


class OrbitRepository(RepositoryBase, CrudMixin):
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

            if not db_orbit:
                return None

            db_orbit.members.sort(
                key=lambda m: {OrbitRole.ADMIN: 1, OrbitRole.MEMBER: 2}.get(
                    OrbitRole(m.role), 3
                )
            )

            return db_orbit.to_orbit_details()

    async def get_orbit_simple(self, orbit_id: int) -> Orbit | None:
        async with self._get_session() as session, session.begin():
            result = await session.execute(
                select(OrbitOrm).where(OrbitOrm.id == orbit_id)
            )
            db_orbit = result.scalar_one_or_none()

            return db_orbit.to_orbit() if db_orbit else None

    async def create_orbit(
        self, organization_id: int, orbit: OrbitCreateIn
    ) -> OrbitDetails | None:
        async with self._get_session() as session:
            orbit_create = OrbitCreate(
                name=orbit.name,
                bucket_secret_id=orbit.bucket_secret_id,
                organization_id=organization_id,
            )
            db_orbit = await self.create_model(session, OrbitOrm, orbit_create)

            if orbit.members:
                await self.create_models(
                    session,
                    OrbitMembersOrm,
                    convert_orbit_simple_members(db_orbit.id, orbit.members),
                )

            return await self.get_orbit(db_orbit.id)

    async def update_orbit(self, orbit_id: int, orbit: OrbitUpdate) -> Orbit | None:
        orbit.id = orbit_id

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
            result = await session.execute(
                select(OrbitMembersOrm)
                .filter(OrbitMembersOrm.orbit_id == orbit_id)
                .order_by(
                    case(
                        (OrbitMembersOrm.role == OrbitRole.ADMIN, 1),
                        (OrbitMembersOrm.role == OrbitRole.MEMBER, 2),
                        else_=3,
                    ),
                )
            )
            db_orbit_members = result.scalars().all()
            return [member.to_orbit_member() for member in db_orbit_members]

    async def get_orbit_member(self, member_id: int) -> OrbitMember | None:
        async with self._get_session() as session:
            result = await session.execute(
                select(OrbitMembersOrm).where(OrbitMembersOrm.id == member_id)
            )
            db_member = result.scalar_one_or_none()
            return db_member.to_orbit_member() if db_member else None

    async def get_orbit_member_where(self, *where_conditions) -> OrbitMembersOrm | None:
        async with self._get_session() as session:
            result = await session.execute(
                select(OrbitMembersOrm).where(*where_conditions)
            )
            return result.scalar_one_or_none()

    async def create_orbit_member(self, member: OrbitMemberCreate) -> OrbitMember:
        async with self._get_session() as session:
            db_member = await self.create_model(session, OrbitMembersOrm, member)
            return db_member.to_orbit_member()

    async def create_orbit_members(
        self, members: list[OrbitMemberCreate]
    ) -> list[OrbitMember]:
        async with self._get_session() as session:
            db_members = await self.create_models(session, OrbitMembersOrm, members)
            return [member.to_orbit_member() for member in db_members]

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

    async def get_orbit_member_role(self, orbit_id: int, user_id: int) -> str | None:
        member = await self.get_orbit_member_where(
            OrbitMembersOrm.orbit_id == orbit_id, OrbitMembersOrm.user_id == user_id
        )
        return str(member.role) if member else None
