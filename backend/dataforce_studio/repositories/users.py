from pydantic import EmailStr
import uuid
from typing import Literal

from sqlalchemy import select
import uuid

from pydantic import EmailStr, HttpUrl
from sqlalchemy import func, select

from dataforce_studio.models.organization import (
    Organization,
    OrganizationMember,
    OrgRole,
)
from dataforce_studio.models.organization import DBOrganization, DBOrganizationMember, OrgRole
from dataforce_studio.models.orm import DBUser
from dataforce_studio.models.orm.organization import (
    OrganizationMemberOrm,
    OrganizationOrm,
)
from dataforce_studio.models.orm.user import UserOrm
from dataforce_studio.models.user import CreateUser, UpdateUser, User
from dataforce_studio.repositories.base import RepositoryBase
from dataforce_studio.utils.organizations import generate_organization_name


class UserRepository(RepositoryBase):
    async def create_user(
        self,
        create_user: CreateUser,
    ) -> User:
        async with self._get_session() as session:
            db_user = UserOrm.from_user(create_user)
            session.add(db_user)

            await session.flush()
            await session.refresh(db_user)
            user_response = db_user.to_user()

            db_organization = OrganizationOrm(
                name=generate_organization_name(
                    create_user.email, create_user.full_name
                )
            )
            session.add(db_organization)
            await session.flush()

            db_organization_member = OrganizationMemberOrm(
                user_id=db_user.id,
                organization_id=db_organization.id,
                role=OrgRole.OWNER,
            )
            session.add(db_organization_member)

            await session.commit()
        return user_response

    async def get_user(self, email: EmailStr) -> User | None:
        async with self._get_session() as session:
            result = await session.execute(
                select(UserOrm).filter(UserOrm.email == email)
            )
            db_user = result.scalar_one_or_none()
            return db_user.to_user() if db_user else None

    async def delete_user(self, email: EmailStr) -> None:
        async with self._get_session() as session:
            result = await session.execute(
                select(UserOrm).filter(UserOrm.email == email)
            )
            user = result.scalar_one_or_none()

            if user:
                await session.delete(user)
                await session.commit()

    async def update_user(
        self,
        update_user: UpdateUser,
    ) -> bool:
        async with self._get_session() as session:
            changed = False
            result = await session.execute(
                select(UserOrm).filter(UserOrm.email == update_user.email)
            )

            if not (db_user := result.scalars().first()):
                return False

            fields_to_update = update_user.model_dump(exclude_unset=True)

            for field, value in fields_to_update.items():
                setattr(db_user, field, value)
                changed = True

            if changed:
                await session.commit()
        return changed

    async def create_organization(
        self, name: str, logo: HttpUrl | None = None
    ) -> OrganizationOrm:
        async with self._get_session() as session:
            db_organization = OrganizationOrm(name=name, logo=logo)
            session.add(db_organization)
            await session.commit()
        return db_organization

    async def get_organization_members_count(self, organization_id: uuid.UUID) -> int:
        async with self._get_session() as session:
            result = await session.execute(
                select(func.count())
                .select_from(OrganizationMemberOrm)
                .where(OrganizationMemberOrm.organization_id == organization_id)
            )
        return result.scalar() or 0

    async def create_organization_member(
        self, user_id: uuid.UUID, organization_id: uuid.UUID, role: OrgRole
    ) -> OrganizationMember:
        async with self._get_session() as session:
            db_organization_member = OrganizationMemberOrm(
                user_id=user_id, organization_id=organization_id, role=role
            )
            session.add(db_organization_member)
            await session.commit()
        return db_organization_member.to_organization_member()

    async def create_owner(
        self, user_id: uuid.UUID, organization_id: uuid.UUID
    ) -> OrganizationMember:
        return await self.create_organization_member(
            user_id, organization_id, OrgRole.OWNER
        )

    async def get_user_organizations(
        self, user_id: uuid.UUID, role: OrgRole | None = None
    ) -> list[Organization]:
        async with self._get_session() as session:
            query = (
                select(OrganizationOrm)
                .join(OrganizationMemberOrm)
                .filter(OrganizationMemberOrm.user_id == user_id)
            )

            if role is not None:
                query = query.filter(OrganizationMemberOrm.role == role)

            result = await session.execute(query)
            db_organizations = result.scalars().all()

            return [org.to_organization() for org in db_organizations]

    async def get_organization_users(
        self, organization_id: uuid.UUID, role: OrgRole | None = None
    ) -> list[OrganizationMember]:
        async with self._get_session() as session:
            query = select(OrganizationMemberOrm).filter(
                OrganizationMemberOrm.organization_id == organization_id
            )

            if role is not None:
                query = query.filter(OrganizationMemberOrm.role == role)

            result = await session.execute(query)
            db_organization_members = result.scalars().all()
            return [
                member.to_organization_member() for member in db_organization_members
            ]
