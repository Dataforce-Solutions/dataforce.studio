import uuid

from sqlalchemy import select

from dataforce_studio.models.organization import DBOrganizationInvite
from dataforce_studio.repositories.base import RepositoryBase


class InviteRepository(RepositoryBase):
    async def create_organization_invite(
            self,
            invite: DBOrganizationInvite
    ) -> DBOrganizationInvite:
        async with self._get_session() as session:
            session.add(invite)
            await session.commit()
        return invite

    async def delete_organization_invite(self, invite_id: uuid.UUID) -> None:
        async with self._get_session() as session, session.begin():
            result = await session.execute(
                select(DBOrganizationInvite)
                .filter(DBOrganizationInvite.id == invite_id)
            )
            invite = result.scalar_one_or_none()

            if invite:
                await session.delete(invite)
