from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dataforce_studio.models.base import Base, TimestampMixin
from dataforce_studio.schemas.ml_models import MLModel, MLModelStatus


class MLModelOrm(TimestampMixin, Base):
    __tablename__ = "ml_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    collection_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("collections.id", ondelete="CASCADE"), nullable=False
    )
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    model_name: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str] = mapped_column(String, nullable=True)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    manifest: Mapped[dict] = mapped_column(JSONB, nullable=False)
    file_hash: Mapped[str] = mapped_column(String, nullable=False)
    file_index: Mapped[dict[str, tuple[int, int]]] = mapped_column(
        JSONB, nullable=False
    )
    bucket_location: Mapped[str] = mapped_column(String, nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    unique_identifier: Mapped[str] = mapped_column(String, nullable=False)
    tags: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True, default=list)
    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default=MLModelStatus.PENDING_UPLOAD.value,
    )

    collection: Mapped["CollectionOrm"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "CollectionOrm", back_populates="models", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"MLModel(id={self.id!r}, identifier={self.unique_identifier!r})"

    def to_ml_model(self) -> MLModel:
        return MLModel.model_validate(self)
