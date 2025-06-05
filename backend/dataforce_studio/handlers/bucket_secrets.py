from dataforce_studio.handlers.permissions import PermissionsHandler
from dataforce_studio.infra.db import engine
from dataforce_studio.infra.exceptions import NotFoundError
from dataforce_studio.repositories.bucket_secrets import BucketSecretRepository
from dataforce_studio.schemas.bucket_secrets import (
    BucketSecret,
    BucketSecretCreate,
    BucketSecretCreateIn,
    BucketSecretUpdate,
)
from dataforce_studio.schemas.permissions import Action, Resource


class BucketSecretHandler:
    __secret_repository = BucketSecretRepository(engine)
    __permissions_handler = PermissionsHandler()

    async def create_bucket_secret(
        self, user_id: int, organization_id: int, secret: BucketSecretCreateIn
    ) -> BucketSecret:
        await self.__permissions_handler.check_organization_permission(
            organization_id, user_id, Resource.BUCKET_SECRET, Action.CREATE
        )
        secret = BucketSecretCreate(**secret.model_dump(), organization_id=organization_id)
        return await self.__secret_repository.create_bucket_secret(secret)

    async def get_organization_bucket_secrets(
        self, user_id: int, organization_id: int
    ) -> list[BucketSecret]:
        await self.__permissions_handler.check_organization_permission(
            organization_id, user_id, Resource.BUCKET_SECRET, Action.LIST
        )
        return await self.__secret_repository.get_organization_bucket_secrets(
            organization_id
        )

    async def get_bucket_secret(
        self, user_id: int, organization_id: int, secret_id: int
    ) -> BucketSecret:
        await self.__permissions_handler.check_organization_permission(
            organization_id, user_id, Resource.BUCKET_SECRET, Action.READ
        )
        secret = await self.__secret_repository.get_bucket_secret(secret_id)
        if not secret:
            raise NotFoundError("Secret not found")
        return secret

    async def update_bucket_secret(
        self,
        user_id: int,
        organization_id: int,
        secret_id: int,
        secret: BucketSecretUpdate,
    ) -> BucketSecret:
        await self.__permissions_handler.check_organization_permission(
            organization_id, user_id, Resource.BUCKET_SECRET, Action.UPDATE
        )
        secret.id = secret_id
        db_secret = await self.__secret_repository.update_bucket_secret(secret)
        if not db_secret:
            raise NotFoundError("Secret not found")
        return db_secret

    async def delete_bucket_secret(
        self, user_id: int, organization_id: int, secret_id: int
    ) -> None:
        await self.__permissions_handler.check_organization_permission(
            organization_id, user_id, Resource.BUCKET_SECRET, Action.DELETE
        )
        await self.__secret_repository.delete_bucket_secret(secret_id)
