from dataforce_studio.models import BucketSecretOrm
from dataforce_studio.repositories.base import CrudMixin, RepositoryBase
from dataforce_studio.schemas.bucket_secrets import (
    BucketSecret,
    BucketSecretCreate,
    BucketSecretUpdate,
)


class BucketSecretRepository(RepositoryBase, CrudMixin):
    async def create_bucket_secret(self, secret: BucketSecretCreate) -> BucketSecret:
        async with self._get_session() as session:
            db_secret = await self.create_model(session, BucketSecretOrm, secret)
            return db_secret.to_bucket_secret()

    async def get_bucket_secret(self, secret_id: int) -> BucketSecret | None:
        async with self._get_session() as session:
            db_secret = await self.get_model(session, BucketSecretOrm, secret_id)
            return db_secret.to_bucket_secret() if db_secret else None

    async def get_organization_bucket_secrets(
        self, organization_id: int
    ) -> list[BucketSecret]:
        async with self._get_session() as session:
            db_secrets = await self.get_models_where(
                session,
                BucketSecretOrm,
                BucketSecretOrm.organization_id == organization_id,
            )
            return [secret.to_bucket_secret() for secret in db_secrets]

    async def update_bucket_secret(
        self, secret: BucketSecretUpdate
    ) -> BucketSecret | None:
        async with self._get_session() as session:
            db_secret = await self.update_model(session, BucketSecretOrm, secret)
            return db_secret.to_bucket_secret() if db_secret else None

    async def delete_bucket_secret(self, secret_id: int) -> None:
        async with self._get_session() as session:
            return await self.delete_model(session, BucketSecretOrm, secret_id)
