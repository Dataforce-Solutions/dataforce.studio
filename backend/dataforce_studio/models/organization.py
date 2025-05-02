import uuid
from enum import StrEnum

from pydantic import EmailStr, HttpUrl
from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dataforce_studio.models.base import Base, TimestampMixin


class OrgRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class DBOrganization(TimestampMixin, Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, unique=True, nullable=False, default=uuid.uuid4
    )
    name: Mapped[str | None] = mapped_column(String, nullable=False)
    logo: Mapped[HttpUrl | None] = mapped_column(String, nullable=True)

    members: Mapped[list["DBOrganizationMember"]] = relationship(
        back_populates="organization", cascade="all, delete, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"Organization(id={self.id!r}, name={self.name!r})"


class DBOrganizationMember(TimestampMixin, Base):
    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="org_member"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, unique=True, nullable=False, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[OrgRole] = mapped_column(Enum(OrgRole), nullable=False)

    organization: Mapped["DBOrganization"] = relationship(back_populates="members")

    def __repr__(self) -> str:
        return (f"OrganizationMember(id={self.id!r}, user={self.user!r}, "
                f"organization={self.organization!r})")
