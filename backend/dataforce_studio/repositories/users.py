from fastapi import HTTPException, status
from pydantic import EmailStr, HttpUrl
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload

from dataforce_studio.models.organization import (
    OrganizationMemberOrm,
    OrganizationOrm,
)
from dataforce_studio.models.stats import StatsEmailSendOrm
from dataforce_studio.models.user import UserOrm
from dataforce_studio.repositories.base import CrudMixin, RepositoryBase
from dataforce_studio.schemas.organization import (
    Organization,
    OrganizationDetails,
    OrganizationMember,
    OrganizationSwitcher,
    OrganizationUpdate,
    OrgRole,
    UpdateOrganizationMember,
)
from dataforce_studio.schemas.stats import StatsEmailSendCreate, StatsEmailSendOut
from dataforce_studio.schemas.user import (
    CreateUser,
    UpdateUser,
    User,
    UserOut,
)
from dataforce_studio.utils.organizations import (
    generate_organization_name,
    get_members_roles_count,
)


class UserRepository(RepositoryBase, CrudMixin):
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

    async def get_public_user(self, email: EmailStr) -> UserOut | None:
        async with self._get_session() as session:
            result = await session.execute(
                select(UserOrm).filter(UserOrm.email == email)
            )
            db_user = result.scalar_one_or_none()
            return db_user.to_public_user() if db_user else None

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
        self, user_id: int, name: str, logo: HttpUrl | None = None
    ) -> OrganizationOrm:
        async with self._get_session() as session:
            org_logo = str(logo) if logo else None
            db_organization = OrganizationOrm(name=name, logo=org_logo)
            session.add(db_organization)
            await session.commit()
            await session.refresh(db_organization)

            db_organization_member = OrganizationMemberOrm(
                user_id=user_id,
                organization_id=db_organization.id,
                role=OrgRole.OWNER,
            )
            session.add(db_organization_member)

            await session.commit()
            await session.refresh(db_organization)
            return db_organization

    async def update_organization(
        self,
        organization_id: int,
        organization: OrganizationUpdate,
    ) -> Organization | None:
        organization.id = organization_id
        organization.logo = str(organization.logo) if organization.logo else None

        async with self._get_session() as session:
            db_organization = await self.update_model(
                session=session, orm_class=OrganizationOrm, data=organization
            )
            return db_organization.to_organization() if db_organization else None

    async def delete_organization(self, organization_id: int) -> None:
        async with self._get_session() as session:
            return await self.delete_model(session, OrganizationOrm, organization_id)

    async def get_organization_members_count(self, organization_id: int) -> int:
        async with self._get_session() as session:
            result = await session.execute(
                select(func.count())
                .select_from(OrganizationMemberOrm)
                .where(OrganizationMemberOrm.organization_id == organization_id)
            )
        return result.scalar() or 0

    async def create_organization_member(
        self, user_id: int, organization_id: int, role: OrgRole
    ) -> OrganizationMember:
        async with self._get_session() as session:
            db_organization_member = OrganizationMemberOrm(
                user_id=user_id, organization_id=organization_id, role=role
            )
            session.add(db_organization_member)
            try:
                await session.commit()
                await session.refresh(db_organization_member)
            except IntegrityError as e:
                await session.rollback()
                if "org_member" in str(e.orig):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"User with ID {user_id} is already a member "
                        f"of organization {organization_id}.",
                    ) from e
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="An unexpected database error occurred.",
                ) from e
        return OrganizationMember.model_validate(db_organization_member)

    async def create_owner(
        self, user_id: int, organization_id: int
    ) -> OrganizationMember:
        return await self.create_organization_member(
            user_id, organization_id, OrgRole.OWNER
        )

    async def get_user_organizations(
        self, user_id: int, role: OrgRole | None = None
    ) -> list[OrganizationSwitcher]:
        async with self._get_session() as session:
            query = (
                select(OrganizationOrm, OrganizationMemberOrm.role)
                .join(
                    OrganizationMemberOrm,
                    OrganizationMemberOrm.organization_id == OrganizationOrm.id,
                )
                .filter(OrganizationMemberOrm.user_id == user_id)
                .order_by(OrganizationOrm.name)
            )

            if role is not None:
                query = query.filter(OrganizationMemberOrm.role == role)

            result = await session.execute(query)
            db_organizations = result.unique().all()

            return [
                OrganizationSwitcher(
                    id=org.id,
                    name=org.name,
                    logo=org.logo,
                    role=member_role,
                    created_at=org.created_at,
                    updated_at=org.updated_at,
                )
                for org, member_role in db_organizations
            ]

    async def get_organization_details(
        self, organization_id: int
    ) -> OrganizationDetails | None:
        async with self._get_session() as session:
            result = await session.execute(
                select(OrganizationOrm)
                .options(
                    joinedload(OrganizationOrm.members).joinedload(
                        OrganizationMemberOrm.user
                    ),
                    joinedload(OrganizationOrm.invites),
                    joinedload(OrganizationOrm.orbits),
                )
                .where(OrganizationOrm.id == organization_id)
            )
            db_organization = result.unique().scalar_one_or_none()

            if not db_organization:
                return None

            details = OrganizationDetails.model_validate(db_organization)
            details.total_orbits = len(db_organization.orbits)
            details.total_members = len(db_organization.members)
            details.members_by_role = get_members_roles_count(db_organization.members)
            details.members_limit = 50
            details.orbits_limit = 10

            return details

    async def get_organization_users(
        self, organization_id: int, role: OrgRole | None = None
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

    async def update_organization_member_where(
        self, member: UpdateOrganizationMember, *where_conditions
    ) -> OrganizationMember | None:
        async with self._get_session() as session:
            result = await session.execute(
                select(OrganizationMemberOrm).where(*where_conditions)
            )
            db_member = result.scalar_one_or_none()

            if not db_member:
                return None

            fields_to_update = member.model_dump(exclude_unset=True)
            if not fields_to_update:
                return db_member.to_organization_member()

            for field, value in fields_to_update.items():
                setattr(db_member, field, value)

            await session.commit()
            await session.refresh(db_member)

            return db_member.to_organization_member()

    async def update_organization_member(
        self, member_id: int, member: UpdateOrganizationMember
    ) -> OrganizationMember | None:
        return await self.update_organization_member_where(
            member, OrganizationMemberOrm.id == member_id
        )

    async def delete_organization_member_where(self, *where_conditions) -> None:
        async with self._get_session() as session:
            result = await session.execute(
                select(OrganizationMemberOrm).where(*where_conditions)
            )
            member = result.scalar_one_or_none()

            if member:
                await session.delete(member)
                await session.commit()

    async def delete_organization_member(self, member_id: int) -> None:
        return await self.delete_organization_member_where(
            OrganizationMemberOrm.id == member_id
        )

    async def get_organization_members_where(
        self, *where_conditions
    ) -> list[OrganizationMember]:
        async with self._get_session() as session, session.begin():
            result = await session.execute(
                select(OrganizationMemberOrm)
                .options(joinedload(OrganizationMemberOrm.user))
                .where(*where_conditions)
                .order_by(
                    case(
                        (OrganizationMemberOrm.role == "OWNER", 0),
                        (OrganizationMemberOrm.role == "ADMIN", 1),
                        (OrganizationMemberOrm.role == "MEMBER", 2),
                        else_=3,
                    ),
                    OrganizationMemberOrm.created_at,
                )
            )
            members = result.scalars().all()
            return [OrganizationMember.model_validate(member) for member in members]

    async def get_organization_members(
        self, organization_id: int
    ) -> list[OrganizationMember]:
        return await self.get_organization_members_where(
            OrganizationMemberOrm.organization_id == organization_id
        )

    async def get_organization_member(
        self, organization_id: int, user_id: int
    ) -> OrganizationMemberOrm | None:
        async with self._get_session() as session:
            result = await session.execute(
                select(OrganizationMemberOrm).where(
                    OrganizationMemberOrm.user_id == user_id,
                    OrganizationMemberOrm.organization_id == organization_id,
                )
            )
            return result.scalar_one_or_none()

    async def get_organization_member_by_id(
        self, member_id: int
    ) -> OrganizationMember | None:
        async with self._get_session() as session:
            result = await session.execute(
                select(OrganizationMemberOrm).where(
                    OrganizationMemberOrm.id == member_id
                )
            )
            db_member = result.scalar_one_or_none()
            return db_member.to_organization_member() if db_member else None

    async def get_organization_member_by_email(
        self, organization_id: int, email: EmailStr
    ) -> OrganizationMember | None:
        async with self._get_session() as session:
            result = await session.execute(
                select(OrganizationMemberOrm)
                .join(OrganizationMemberOrm.user)
                .where(
                    OrganizationMemberOrm.organization_id == organization_id,
                    UserOrm.email == email,
                )
                .options(selectinload(OrganizationMemberOrm.user))
            )
            db_member = result.scalar_one_or_none()
            return db_member.to_organization_member() if db_member else None

    async def get_organization_member_role(
        self, organization_id: int, user_id: int
    ) -> str | None:
        member = await self.get_organization_member(organization_id, user_id)
        return str(member.role) if member else None

    async def create_stats_email_send_obj(
        self, stat: StatsEmailSendCreate
    ) -> StatsEmailSendOut:
        async with self._get_session() as session:
            db_email_send = StatsEmailSendOrm(
                email=stat.email, description=stat.description
            )
            session.add(db_email_send)
            await session.commit()
            await session.refresh(db_email_send)
        return db_email_send.to_email_send()
