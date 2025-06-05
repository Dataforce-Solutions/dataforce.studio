from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dataforce_studio.models.base import Base, TimestampMixin
from dataforce_studio.schemas.bucket_secrets import BucketSecret


class BucketSecretOrm(TimestampMixin, Base):
    __tablename__ = "bucket_secrets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    endpoint: Mapped[str] = mapped_column(String, nullable=False)
    access_key: Mapped[str | None] = mapped_column(String, nullable=True)
    secret_key: Mapped[str | None] = mapped_column(String, nullable=True)
    session_token: Mapped[str | None] = mapped_column(String, nullable=True)
    secure: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    region: Mapped[str | None] = mapped_column(String, nullable=True)
    cert_check: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    organization: Mapped["OrganizationOrm"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "OrganizationOrm", back_populates="bucket_secrets", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"BucketSecret(id={self.id!r}, endpoint={self.endpoint!r})"

    def to_bucket_secret(self) -> BucketSecret:
        return BucketSecret.model_validate(self)
