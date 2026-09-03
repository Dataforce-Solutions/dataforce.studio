from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from luml.schemas.artifacts import ArtifactListed
from luml.schemas.base import BaseOrmConfig


class LineageVia(StrEnum):
    UI = "ui"
    API = "api"


class LineageNodeRef(BaseModel):
    artifact_id: UUID | None = None
    node_id: UUID | None = None

    @model_validator(mode="after")
    def validate_single_reference(self) -> Self:
        if (self.artifact_id is None) == (self.node_id is None):
            raise ValueError("Exactly one lineage node reference must be set")
        return self


class LineagePosition(BaseModel):
    ref: LineageNodeRef
    x: float
    y: float


class LineagePair(BaseModel):
    source: LineageNodeRef
    target: LineageNodeRef


class LineageCreateIn(BaseModel):
    target_artifact_ids: list[UUID]


class LineageBatchIn(BaseModel):
    create: list[LineagePair] = Field(default_factory=list)
    delete: list[UUID] = Field(default_factory=list)
    positions: list[LineagePosition] = Field(default_factory=list)


class LineageEdge(BaseModel, BaseOrmConfig):
    id: UUID
    source: UUID
    target: UUID
    created_by_user: str
    created_via: LineageVia
    created_at: datetime


class LineageNode(BaseModel):
    id: UUID
    artifact_id: UUID | None
    type: str
    name: str
    collection_name: str | None
    x: float | None
    y: float | None
    is_deleted: bool
    data: ArtifactListed | None


class LineageGraph(BaseModel):
    nodes: list[LineageNode]
    edges: list[LineageEdge]
    focal_artifact_id: UUID
    depth: int
    truncated: bool


class LineageBatchResult(BaseModel):
    created: list[LineageEdge]
    deleted: list[LineageEdge]
