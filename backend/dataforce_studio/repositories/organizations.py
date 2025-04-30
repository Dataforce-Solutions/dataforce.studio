from pydantic import HttpUrl

from dataforce_studio.models.organization import DBOrganization
from dataforce_studio.repositories.base import RepositoryBase


class OrganizationRepository(RepositoryBase):
    async def create_organization(
            self,
            name: str,
            logo: HttpUrl | None = None
    ) -> DBOrganization:
        async with self._get_session() as session:
            db_organization = DBOrganization(name=name, logo=logo)
            session.add(db_organization)
            await session.commit()
        return db_organization
