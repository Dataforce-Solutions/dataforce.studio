from sqlalchemy.orm import joinedload

from dataforce_studio.models.api_keys import APIKeyOrm
from dataforce_studio.repositories.base import CrudMixin, RepositoryBase
from dataforce_studio.schemas.api_keys import (
    APIKeyAuthOut,
    APIKeyCreate,
    APIKeyCreateOut,
    APIKeyOut,
)


class APIKeyRepository(RepositoryBase, CrudMixin):
    async def create_api_key(self, key: APIKeyCreate) -> APIKeyCreateOut:
        async with self._get_session() as session:
            db_key = await self.create_model(session, APIKeyOrm, key)
            return db_key.to_api_key_full()

    async def get_api_key(self, key_id: int) -> APIKeyOut | None:
        async with self._get_session() as session:
            db_key = await self.get_model(session, APIKeyOrm, key_id)
            return db_key.to_api_key() if db_key else None

    async def get_api_key_by_user_id(self, user_id: int) -> APIKeyOut | None:
        async with self._get_session() as session:
            db_key = await self.get_model_where(
                session, APIKeyOrm, APIKeyOrm.user_id == user_id
            )
            return db_key.to_api_key() if db_key else None

    async def get_api_key_by_hash(self, key: str) -> APIKeyAuthOut | None:
        async with self._get_session() as session:
            db_key = await self.get_model_where(
                session,
                APIKeyOrm,
                APIKeyOrm.key == key,
                options=[joinedload(APIKeyOrm.user)],
            )
            return db_key.to_api_key_with_user() if db_key else None

    async def delete_api_key(self, key_id: int) -> None:
        async with self._get_session() as session:
            await self.delete_model(session, APIKeyOrm, key_id)
