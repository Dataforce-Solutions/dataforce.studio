from datetime import datetime

from pydantic import BaseModel

from dataforce_studio.schemas.base import BaseOrmConfig


class ModelCollectionCreate(BaseModel):
    orbit_id: int
    description: str
    name: str
    status: str


class ModelCollection(BaseModel, BaseOrmConfig):
    id: int
    orbit_id: int
    description: str
    name: str
    status: str
    created_at: datetime
    updated_at: datetime | None = None


class ModelVersionCreate(BaseModel):
    model_collection_id: int
    metrics: dict
    bucket_location: str
    size: int
    unique_identifier: str


class ModelVersion(BaseModel, BaseOrmConfig):
    id: int
    model_collection_id: int
    metrics: dict
    bucket_location: str
    size: int
    unique_identifier: str
    created_at: datetime
    updated_at: datetime | None = None
