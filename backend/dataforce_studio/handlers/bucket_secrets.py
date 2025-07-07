from minio import Minio
from minio.error import S3Error

from dataforce_studio.handlers.permissions import PermissionsHandler
from dataforce_studio.infra.db import engine
from dataforce_studio.infra.exceptions import NotFoundError, ServiceError
from dataforce_studio.repositories.bucket_secrets import BucketSecretRepository
from dataforce_studio.schemas.bucket_secrets import (
    BucketSecretCreate,
    BucketSecretCreateIn,
    BucketSecretOut,
    BucketSecretUpdate,
)
from dataforce_studio.schemas.permissions import Action, Resource


class BucketSecretHandler:
    __secret_repository = BucketSecretRepository(engine)
    __permissions_handler = PermissionsHandler()

    def _validate_bucket_credentials(self, secret: BucketSecretCreateIn) -> None:
        try:
            client = Minio(
                endpoint=secret.endpoint,
                access_key=secret.access_key or "",
                secret_key=secret.secret_key or "",
                session_token=secret.session_token,
                secure=secret.secure if secret.secure is not None else True,
                region=secret.region,
                cert_check=secret.cert_check if secret.cert_check is not None else True,
            )

            client.bucket_exists(secret.bucket_name)

        except S3Error as e:
            raise ServiceError("Bucket validation failed") from e
        except Exception as e:
            raise ServiceError("Failed to validate bucket credentials") from e

    async def validate_bucket_credentials(self, secret: BucketSecretCreateIn) -> bool:
        self._validate_bucket_credentials(secret)
        return True

    async def create_bucket_secret(
        self, user_id: int, organization_id: int, secret: BucketSecretCreateIn
    ) -> BucketSecretOut:
        await self.__permissions_handler.check_organization_permission(
            organization_id, user_id, Resource.BUCKET_SECRET, Action.CREATE
        )

        self._validate_bucket_credentials(secret)

        secret_create = BucketSecretCreate(
            **secret.model_dump(), organization_id=organization_id
        )
        created = await self.__secret_repository.create_bucket_secret(secret_create)
        return BucketSecretOut.model_validate(created)

    async def get_organization_bucket_secrets(
        self, user_id: int, organization_id: int
    ) -> list[BucketSecretOut]:
        await self.__permissions_handler.check_organization_permission(
            organization_id, user_id, Resource.BUCKET_SECRET, Action.LIST
        )
        secrets = await self.__secret_repository.get_organization_bucket_secrets(
            organization_id
        )
        return [BucketSecretOut.model_validate(s) for s in secrets]

    async def get_bucket_secret(
        self, user_id: int, organization_id: int, secret_id: int
    ) -> BucketSecretOut:
        await self.__permissions_handler.check_organization_permission(
            organization_id, user_id, Resource.BUCKET_SECRET, Action.READ
        )
        secret = await self.__secret_repository.get_bucket_secret(secret_id)
        if not secret:
            raise NotFoundError("Secret not found")
        return BucketSecretOut.model_validate(secret)

    async def update_bucket_secret(
        self,
        user_id: int,
        organization_id: int,
        secret_id: int,
        secret: BucketSecretUpdate,
    ) -> BucketSecretOut:
        await self.__permissions_handler.check_organization_permission(
            organization_id, user_id, Resource.BUCKET_SECRET, Action.UPDATE
        )
        secret.id = secret_id
        db_secret = await self.__secret_repository.update_bucket_secret(secret)
        if not db_secret:
            raise NotFoundError("Secret not found")
        return BucketSecretOut.model_validate(db_secret)

    async def delete_bucket_secret(
        self, user_id: int, organization_id: int, secret_id: int
    ) -> None:
        await self.__permissions_handler.check_organization_permission(
            organization_id, user_id, Resource.BUCKET_SECRET, Action.DELETE
        )
        await self.__secret_repository.delete_bucket_secret(secret_id)
