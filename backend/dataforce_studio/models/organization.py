import datetime
import uuid
from enum import StrEnum

from pydantic import EmailStr, HttpUrl
from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dataforce_studio.models.base import Base


class OrgRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class DBOrganization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, unique=True, nullable=False, default=uuid.uuid4
    )
    name: Mapped[str | None] = mapped_column(String, nullable=False)
    logo: Mapped[HttpUrl | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.UTC)
    )

    members: Mapped[list["DBOrganizationMember"]] = relationship(
        back_populates="organization", cascade="all, delete, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"Organization(id={self.id!r}, name={self.name!r})"


class DBOrganizationMember(Base):
    __tablename__ = "organization_members"
    __table_args__ = {UniqueConstraint("organization_id", "user", name="org_member")}

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, unique=True, nullable=False, default=uuid.uuid4
    )
    user: Mapped[EmailStr] = mapped_column(
        String, ForeignKey("users.email", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[OrgRole] = mapped_column(Enum(OrgRole), nullable=False)
    joined_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.UTC)
    )

    organization: Mapped["DBOrganization"] = relationship(back_populates="members")

    def __repr__(self) -> str:
        return (f"OrganizationMember(id={self.id!r}, user={self.user!r}, "
                f"organization={self.organization!r})")
