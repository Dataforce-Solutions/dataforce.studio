from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dataforce_studio.models.base import Base, TimestampMixin
from dataforce_studio.schemas.ml_models import ModelCollection, ModelVersion


class ModelCollectionOrm(TimestampMixin, Base):
    __tablename__ = "model_collections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    orbit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("orbits.id", ondelete="CASCADE"), nullable=False
    )
    description: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)

    orbit: Mapped["OrbitOrm"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "OrbitOrm", back_populates="model_collections", lazy="selectin"
    )
    versions: Mapped[list["ModelVersionOrm"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="model_collection", cascade="all, delete, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"ModelCollection(id={self.id!r}, name={self.name!r})"

    def to_model_collection(self) -> ModelCollection:
        return ModelCollection.model_validate(self)


class ModelVersionOrm(TimestampMixin, Base):
    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_collection_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("model_collections.id", ondelete="CASCADE"), nullable=False
    )
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False)
    bucket_location: Mapped[str] = mapped_column(String, nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    unique_identifier: Mapped[str] = mapped_column(String, nullable=False)

    model_collection: Mapped["ModelCollectionOrm"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "ModelCollectionOrm", back_populates="versions", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"ModelVersion(id={self.id!r}, identifier={self.unique_identifier!r})"

    def to_model_version(self) -> ModelVersion:
        return ModelVersion.model_validate(self)
