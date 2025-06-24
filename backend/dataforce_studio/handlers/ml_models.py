from datetime import timedelta
from uuid import uuid4

from fastapi import status
from minio import Minio

from dataforce_studio.handlers.permissions import PermissionsHandler
from dataforce_studio.infra.db import engine
from dataforce_studio.infra.exceptions import NotFoundError, ServiceError
from dataforce_studio.repositories.bucket_secrets import BucketSecretRepository
from dataforce_studio.repositories.collections import CollectionRepository
from dataforce_studio.repositories.ml_models import MLModelRepository
from dataforce_studio.repositories.orbits import OrbitRepository
from dataforce_studio.schemas.ml_models import (
    Collection,
    MLModel,
    MLModelCreate,
    MLModelIn,
    MLModelStatus,
    MLModelUpdate,
    MLModelUpdateIn,
)
from dataforce_studio.schemas.orbit import Orbit
from dataforce_studio.schemas.permissions import Action, Resource


class MLModelHandler:
    __repository = MLModelRepository(engine)
    __orbit_repository = OrbitRepository(engine)
    __secret_repository = BucketSecretRepository(engine)
    __collection_repository = CollectionRepository(engine)
    __permissions_handler = PermissionsHandler()

    async def _get_presigned_url(self, secret_id: int, object_name: str) -> str:
        secret = await self.__secret_repository.get_bucket_secret(secret_id)
        if not secret:
            raise NotFoundError("Bucket secret not found")

        client = Minio(
            secret.endpoint,
            access_key=secret.access_key,
            secret_key=secret.secret_key,
            session_token=secret.session_token,
            secure=secret.secure if secret.secure is not None else True,
            region=secret.region,
            cert_check=secret.cert_check if secret.cert_check is not None else True,
        )
        return client.presigned_put_object(
            bucket_name=secret.bucket_name,
            object_name=object_name,
            expires=timedelta(hours=1),
        )

    async def _get_download_url(self, secret_id: int, object_name: str) -> str:
        secret = await self.__secret_repository.get_bucket_secret(secret_id)
        if not secret:
            raise NotFoundError("Bucket secret not found")

        client = Minio(
            secret.endpoint,
            access_key=secret.access_key,
            secret_key=secret.secret_key,
            session_token=secret.session_token,
            secure=secret.secure if secret.secure is not None else True,
            region=secret.region,
            cert_check=secret.cert_check if secret.cert_check is not None else True,
        )
        return client.presigned_get_object(
            bucket_name=secret.bucket_name,
            object_name=object_name,
            expires=timedelta(hours=1),
        )

    async def _get_delete_url(self, secret_id: int, object_name: str) -> str:
        secret = await self.__secret_repository.get_bucket_secret(secret_id)
        if not secret:
            raise NotFoundError("Bucket secret not found")

        client = Minio(
            secret.endpoint,
            access_key=secret.access_key,
            secret_key=secret.secret_key,
            session_token=secret.session_token,
            secure=secret.secure if secret.secure is not None else True,
            region=secret.region,
            cert_check=secret.cert_check if secret.cert_check is not None else True,
        )
        return client.get_presigned_url(
            "DELETE",
            bucket_name=secret.bucket_name,
            object_name=object_name,
            expires=timedelta(hours=1),
        )

    async def _check_orbit_and_collection_access(
        self, organization_id: int, orbit_id: int, collection_id: int
    ) -> tuple[Orbit, Collection]:
        orbit = await self.__orbit_repository.get_orbit_simple(
            orbit_id, organization_id
        )
        if not orbit or orbit.organization_id != organization_id:
            raise NotFoundError("Orbit not found")
        collection = await self.__collection_repository.get_collection(collection_id)
        if not collection or collection.orbit_id != orbit_id:
            raise NotFoundError("Collection not found")
        return orbit, collection

    async def create_ml_model(
        self,
        user_id: int,
        organization_id: int,
        orbit_id: int,
        collection_id: int,
        model: MLModelIn,
    ) -> tuple[MLModel, str]:
        await self.__permissions_handler.check_orbit_action_access(
            organization_id,
            orbit_id,
            user_id,
            Resource.MODEL,
            Action.CREATE,
        )

        orbit, collection = await self._check_orbit_and_collection_access(
            organization_id, orbit_id, collection_id
        )
        unique_id = uuid4().hex
        object_name = f"{unique_id}-{model.file_name}"
        bucket_location = f"orbit-{orbit_id}/collection-{collection_id}/{object_name}"

        created_model = await self.__repository.create_ml_model(
            MLModelCreate(
                collection_id=collection_id,
                metrics=model.metrics,
                manifest=model.manifest,
                file_hash=model.file_hash,
                file_index=model.file_index,
                bucket_location=bucket_location,
                size=model.size,
                unique_identifier=unique_id,
                tags=model.tags,
                status=MLModelStatus.PENDING_UPLOAD,
            )
        )

        url = await self._get_presigned_url(orbit.bucket_secret_id, bucket_location)
        return created_model, url

    async def update_model(
        self,
        user_id: int,
        organization_id: int,
        orbit_id: int,
        collection_id: int,
        model_id: int,
        model: MLModelUpdateIn,
    ) -> MLModel:
        await self.__permissions_handler.check_orbit_action_access(
            organization_id,
            orbit_id,
            user_id,
            Resource.MODEL,
            Action.UPDATE,
        )
        await self._check_orbit_and_collection_access(
            organization_id, orbit_id, collection_id
        )
        updated = await self.__repository.update_ml_model(
            model_id,
            MLModelUpdate(id=model_id, tags=model.tags, status=model.status),
        )
        if not updated:
            raise NotFoundError("ML model not found")
        return updated

    async def request_download_url(
        self,
        user_id: int,
        organization_id: int,
        orbit_id: int,
        collection_id: int,
        model_id: int,
    ) -> str:
        await self.__permissions_handler.check_orbit_action_access(
            organization_id,
            orbit_id,
            user_id,
            Resource.MODEL,
            Action.READ,
        )

        orbit, collection = await self._check_orbit_and_collection_access(
            organization_id, orbit_id, collection_id
        )
        model = await self.__repository.get_ml_model(model_id)
        if not model:
            raise NotFoundError("ML model not found")

        return await self._get_download_url(
            orbit.bucket_secret_id,
            model.bucket_location,
        )

    async def request_delete_url(
        self,
        user_id: int,
        organization_id: int,
        orbit_id: int,
        collection_id: int,
        model_id: int,
    ) -> str:
        await self.__permissions_handler.check_orbit_action_access(
            organization_id,
            orbit_id,
            user_id,
            Resource.MODEL,
            Action.UPDATE,
        )
        await self._check_orbit_and_collection_access(
            organization_id, orbit_id, collection_id
        )
        model = await self.__repository.get_ml_model(model_id)
        if not model:
            raise NotFoundError("ML model not found")

        orbit = await self.__orbit_repository.get_orbit_simple(
            orbit_id, organization_id
        )
        if not orbit:
            raise NotFoundError("Orbit not found")

        url = await self._get_delete_url(orbit.bucket_secret_id, model.bucket_location)
        await self.__repository.update_status(model_id, MLModelStatus.PENDING_DELETION)
        return url

    async def confirm_deletion(
        self,
        user_id: int,
        organization_id: int,
        orbit_id: int,
        collection_id: int,
        model_id: int,
    ) -> None:
        await self.__permissions_handler.check_orbit_action_access(
            organization_id,
            orbit_id,
            user_id,
            Resource.MODEL,
            Action.DELETE,
        )
        await self._check_orbit_and_collection_access(
            organization_id, orbit_id, collection_id
        )
        model = await self.__repository.get_ml_model(model_id)
        if not model:
            raise NotFoundError("ML model not found")
        if model.status != MLModelStatus.PENDING_DELETION:
            raise ServiceError(
                f"Unable to confirm deletion with status '{model.status}'",
                status_code=status.HTTP_409_CONFLICT,
            )
        await self.__repository.delete_ml_model(model_id)

    async def get_collection_models(
        self,
        user_id: int,
        organization_id: int,
        orbit_id: int,
        collection_id: int,
    ) -> list[MLModel]:
        await self.__permissions_handler.check_orbit_action_access(
            organization_id,
            orbit_id,
            user_id,
            Resource.MODEL,
            Action.LIST,
        )
        await self._check_orbit_and_collection_access(
            organization_id, orbit_id, collection_id
        )
        return await self.__repository.get_collection_models(collection_id)

    async def get_ml_model(
        self,
        user_id: int,
        organization_id: int,
        orbit_id: int,
        collection_id: int,
        model_id: int,
    ) -> tuple[MLModel, str]:
        await self.__permissions_handler.check_orbit_action_access(
            organization_id,
            orbit_id,
            user_id,
            Resource.MODEL,
            Action.READ,
        )
        orbit, _ = await self._check_orbit_and_collection_access(
            organization_id, orbit_id, collection_id
        )
        model = await self.__repository.get_ml_model(model_id)
        if not model:
            raise NotFoundError("ML model not found")

        url = await self._get_download_url(
            orbit.bucket_secret_id, model.bucket_location
        )
        return model, url
