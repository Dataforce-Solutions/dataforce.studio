import uuid
from enum import StrEnum

from pydantic import HttpUrl
from sqlalchemy import UUID, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dataforce_studio.models.base import Base, TimestampMixin
from dataforce_studio.models.orm import UserOrm


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

    invites: Mapped[list["DBOrganizationInvite"]] = relationship(
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

    role: Mapped[str] = mapped_column(String, nullable=False)
    user: Mapped["UserOrm"] = relationship(
        "UserOrm", back_populates="memberships", lazy="selectin"
    )
    organization: Mapped["DBOrganization"] = relationship(back_populates="members")

    def __repr__(self) -> str:
        return (
            f"OrganizationMember(id={self.id!r}, user_id={self.user_id!r}, "
            f"organization={self.organization.id!r})"
        )


class DBOrganizationInvite(TimestampMixin, Base):
    __tablename__ = "organization_invites"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, unique=True, nullable=False, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    invited_by: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("users.id"), nullable=False
    )

    organization: Mapped["DBOrganization"] = relationship(back_populates="invites")

    def __repr__(self) -> str:
        return (
            f"OrganizationInvite(id={self.id!r}, email={self.email!r}, "
            f"role={self.role!r}, organization={self.organization.id!r})"
        )
