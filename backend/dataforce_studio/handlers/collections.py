from fastapi import status

from dataforce_studio.handlers.permissions import PermissionsHandler
from dataforce_studio.infra.db import engine
from dataforce_studio.infra.exceptions import CollectionDeleteError, NotFoundError
from dataforce_studio.repositories.collections import CollectionRepository
from dataforce_studio.repositories.ml_models import MLModelRepository
from dataforce_studio.repositories.orbits import OrbitRepository
from dataforce_studio.schemas.ml_models import (
    Collection,
    CollectionCreate,
    CollectionCreateIn,
    CollectionUpdate,
    CollectionUpdateIn,
)
from dataforce_studio.schemas.permissions import Action, Resource


class CollectionHandler:
    __repository = CollectionRepository(engine)
    __orbit_repository = OrbitRepository(engine)
    __permissions_handler = PermissionsHandler()
    __models_repository = MLModelRepository(engine)

    async def create_collection(
        self,
        user_id: int,
        organization_id: int,
        orbit_id: int,
        collection: CollectionCreateIn,
    ) -> Collection:
        await self.__permissions_handler.check_orbit_action_access(
            organization_id,
            orbit_id,
            user_id,
            Resource.COLLECTION,
            Action.CREATE,
        )
        orbit = await self.__orbit_repository.get_orbit_simple(orbit_id)
        if not orbit or orbit.organization_id != organization_id:
            raise NotFoundError("Orbit not found")
        collection_create = CollectionCreate(
            **collection.model_dump(), orbit_id=orbit_id
        )
        return await self.__repository.create_collection(collection_create)

    async def get_orbit_collections(
        self, user_id: int, organization_id: int, orbit_id: int
    ) -> list[Collection]:
        await self.__permissions_handler.check_orbit_action_access(
            organization_id,
            orbit_id,
            user_id,
            Resource.COLLECTION,
            Action.LIST,
        )
        orbit = await self.__orbit_repository.get_orbit_simple(orbit_id)
        if not orbit or orbit.organization_id != organization_id:
            raise NotFoundError("Orbit not found")
        return await self.__repository.get_orbit_collections(orbit_id)

    async def update_collection(
        self,
        user_id: int,
        organization_id: int,
        orbit_id: int,
        collection_id: int,
        collection: CollectionUpdateIn,
    ) -> Collection:
        await self.__permissions_handler.check_orbit_action_access(
            organization_id,
            orbit_id,
            user_id,
            Resource.COLLECTION,
            Action.UPDATE,
        )
        orbit = await self.__orbit_repository.get_orbit_simple(orbit_id)
        if not orbit or orbit.organization_id != organization_id:
            raise NotFoundError("Orbit not found")
        updated = await self.__repository.update_collection(
            collection_id,
            CollectionUpdate(
                id=collection_id,
                description=collection.description,
                name=collection.name,
                tags=collection.tags,
            ),
        )
        if not updated:
            raise NotFoundError("Collection not found")
        return updated

    async def delete_collection(
        self, user_id: int, organization_id: int, orbit_id: int, collection_id: int
    ) -> None:
        await self.__permissions_handler.check_orbit_action_access(
            organization_id,
            orbit_id,
            user_id,
            Resource.COLLECTION,
            Action.DELETE,
        )
        orbit = await self.__orbit_repository.get_orbit_simple(orbit_id)
        if not orbit or orbit.organization_id != organization_id:
            raise NotFoundError("Orbit not found")
        collection = await self.__repository.get_collection(collection_id)
        if not collection:
            raise NotFoundError("Collection not found")
        models_count = await self.__models_repository.get_collection_models_count(
            collection_id
        )
        if models_count:
            raise CollectionDeleteError(
                "Collection has models and cant be deleted",
                status_code=status.HTTP_409_CONFLICT,
            )
        await self.__repository.delete_collection(collection_id)
