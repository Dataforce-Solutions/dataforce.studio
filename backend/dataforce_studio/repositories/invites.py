import uuid

from sqlalchemy import delete, select

from dataforce_studio.infra.exceptions import NotFoundError
from dataforce_studio.models.organization import OrganizationInviteOrm
from dataforce_studio.repositories.base import RepositoryBase
from dataforce_studio.schemas.invite import OrganizationInvite


class InviteRepository(RepositoryBase):
    async def create_organization_invite(
        self, invite: OrganizationInviteOrm
    ) -> OrganizationInvite:
        async with self._get_session() as session:
            session.add(invite)
            await session.commit()
            await session.refresh(invite)
        return invite.to_organization_invite()

    async def delete_organization_invite(self, invite_id: uuid.UUID) -> None:
        async with self._get_session() as session, session.begin():
            result = await session.execute(
                select(OrganizationInviteOrm).filter(
                    OrganizationInviteOrm.id == invite_id
                )
            )
            invite = result.scalar_one_or_none()

            if invite:
                await session.delete(invite)
            else:
                raise NotFoundError("Invite not found")

    async def get_invites_where(self, *where_conditions) -> list[OrganizationInvite]:
        async with self._get_session() as session, session.begin():
            result = await session.execute(
                select(OrganizationInviteOrm).where(*where_conditions)
            )
            invites = result.scalars().all()

            return OrganizationInviteOrm.to_invites_list(invites)

    async def get_invites_by_organization_id(
        self, organization_id: uuid.UUID
    ) -> list[OrganizationInvite]:
        return await self.get_invites_where(
            OrganizationInviteOrm.organization_id == organization_id
        )

    async def get_invites_by_user_email(self, email: str) -> list[OrganizationInvite]:
        return await self.get_invites_where(OrganizationInviteOrm.email == email)

    async def get_invite(self, invite_id: uuid.UUID) -> OrganizationInvite:
        async with self._get_session() as session, session.begin():
            result = await session.execute(
                select(OrganizationInviteOrm).where(
                    OrganizationInviteOrm.id == invite_id
                )
            )

            invite = result.scalar_one_or_none()
            if invite:
                return invite.to_organization_invite()
            raise NotFoundError("Invite not found")

    async def delete_organization_invites_where(self, *conditions) -> None:
        async with self._get_session() as session, session.begin():
            await session.execute(delete(OrganizationInviteOrm).where(*conditions))
            await session.commit()

    async def delete_organization_invites_for_user(
        self, organization_id: uuid.UUID, email: str
    ) -> None:
        return await self.delete_organization_invites_where(
            OrganizationInviteOrm.organization_id == organization_id,
            OrganizationInviteOrm.email == email,
        )
