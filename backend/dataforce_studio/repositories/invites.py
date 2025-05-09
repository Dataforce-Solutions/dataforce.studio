import uuid

from fastapi import HTTPException, status
from sqlalchemy import delete, select

from dataforce_studio.models.invite import OrganizationInvite
from dataforce_studio.models.orm.organization import DBOrganizationInvite
from dataforce_studio.repositories.base import RepositoryBase


class InviteRepository(RepositoryBase):
    async def create_organization_invite(
        self, invite: DBOrganizationInvite
    ) -> DBOrganizationInvite:
        async with self._get_session() as session:
            session.add(invite)
            await session.commit()
            await session.refresh(invite)
        return invite

    async def delete_organization_invite(self, invite_id: uuid.UUID) -> None:
        async with self._get_session() as session, session.begin():
            result = await session.execute(
                select(DBOrganizationInvite).filter(
                    DBOrganizationInvite.id == invite_id
                )
            )
            invite = result.scalar_one_or_none()

            if invite:
                await session.delete(invite)
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found"
                )

    async def get_invites_where(self, *where_conditions) -> list[OrganizationInvite]:
        async with self._get_session() as session, session.begin():
            result = await session.execute(
                select(DBOrganizationInvite).where(*where_conditions)
            )
            invites = result.scalars().all()

            return [OrganizationInvite.model_validate(invite) for invite in invites]

    async def get_invite(self, invite_id: uuid.UUID) -> OrganizationInvite:
        async with self._get_session() as session, session.begin():
            result = await session.execute(
                select(DBOrganizationInvite).where(DBOrganizationInvite.id == invite_id)
            )

            invite = result.scalar_one_or_none()
            if invite:
                return OrganizationInvite.model_validate(invite)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found"
            )

    async def delete_organization_invites_where(self, *conditions) -> None:
        async with self._get_session() as session, session.begin():
            await session.execute(delete(DBOrganizationInvite).where(*conditions))
            await session.commit()
