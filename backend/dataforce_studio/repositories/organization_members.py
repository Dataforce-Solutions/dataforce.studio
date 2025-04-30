import uuid

from pydantic import EmailStr

from dataforce_studio.models.organization import DBOrganizationMember, OrgRole
from dataforce_studio.repositories.base import RepositoryBase


class OrganizationRepository(RepositoryBase):
    async def create_organization_member(
            self,
            user: EmailStr,
            organization_id: uuid.UUID,
            role: OrgRole
    ) -> DBOrganizationMember:
        async with self._get_session() as session:
            db_organization_member = DBOrganizationMember(
                user=user,
                organization_id=organization_id,
                role=role
            )
            session.add(db_organization_member)
            await session.commit()
        return db_organization_member
