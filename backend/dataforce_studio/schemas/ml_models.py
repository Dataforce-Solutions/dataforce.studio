from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel

from dataforce_studio.schemas.base import BaseOrmConfig


class CollectionType(StrEnum):
    MODEL = "model"
    DATASET = "dataset"


class CollectionCreate(BaseModel):
    orbit_id: int
    description: str
    name: str
    collection_type: CollectionType
    tags: list[str] | None = None


class CollectionCreateIn(BaseModel):
    description: str
    name: str
    collection_type: CollectionType
    tags: list[str] | None = None


class Collection(BaseModel, BaseOrmConfig):
    id: int
    orbit_id: int
    description: str
    name: str
    collection_type: CollectionType
    tags: list[str] | None = None
    total_models: int
    created_at: datetime
    updated_at: datetime | None = None


class CollectionUpdate(BaseModel):
    id: int | None = None
    description: str | None = None
    name: str | None = None
    tags: list[str] | None = None


class CollectionUpdateIn(BaseModel):
    description: str | None = None
    name: str | None = None
    tags: list[str] | None = None


class MLModelStatus(StrEnum):
    PENDING_UPLOAD = "pending_upload"
    UPLOADED = "uploaded"
    PENDING_DELETION = "pending_deletion"
    UPLOAD_FAILED = "upload_failed"


class MLModelCreate(BaseModel):
    collection_id: int
    metrics: dict
    manifest: dict
    file_hash: str
    file_index: dict
    bucket_location: str
    size: int
    unique_identifier: str
    tags: list[str] | None = None
    status: MLModelStatus = MLModelStatus.PENDING_UPLOAD


class MLModelIn(BaseModel):
    metrics: dict
    manifest: dict
    file_hash: str
    file_index: dict
    size: int
    file_name: str
    tags: list[str] | None = None


class MLModelUpdate(BaseModel):
    id: int
    status: MLModelStatus | None = None
    tags: list[str] | None = None


class MLModelUpdateIn(BaseModel):
    id: int
    tags: list[str] | None = None


class MLModel(BaseModel, BaseOrmConfig):
    id: int
    collection_id: int
    metrics: dict
    manifest: dict
    file_hash: str
    file_index: dict
    bucket_location: str
    size: int
    unique_identifier: str
    tags: list[str] | None = None
    status: MLModelStatus
    created_at: datetime
    updated_at: datetime | None = None
