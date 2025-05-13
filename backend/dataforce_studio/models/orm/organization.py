import uuid
from collections.abc import Sequence

from pydantic import HttpUrl
from sqlalchemy import UUID, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dataforce_studio.models.invite import OrganizationInvite
from dataforce_studio.models.organization import (
    Organization,
    OrganizationMember,
    OrgRole,
)
from dataforce_studio.models.orm.base import Base, TimestampMixin


class OrganizationOrm(TimestampMixin, Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, unique=True, nullable=False, default=uuid.uuid4
    )
    name: Mapped[str | None] = mapped_column(String, nullable=False)
    logo: Mapped[HttpUrl | None] = mapped_column(String, nullable=True)

    members: Mapped[list["OrganizationMemberOrm"]] = relationship(
        back_populates="organization", cascade="all, delete, delete-orphan"
    )

    invites: Mapped[list["OrganizationInviteOrm"]] = relationship(
        back_populates="organization", cascade="all, delete, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"Organization(id={self.id!r}, name={self.name!r})"

    def to_organization(self) -> Organization:
        return Organization.model_validate(self)


class OrganizationMemberOrm(TimestampMixin, Base):
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
    role: Mapped[OrgRole] = mapped_column(
        Enum(OrgRole, native_enum=False), nullable=False
    )

    organization: Mapped["OrganizationOrm"] = relationship(back_populates="members")

    def __repr__(self) -> str:
        return (
            f"OrganizationMember(id={self.id!r}, user_id={self.user_id!r}, "
            f"organization={self.organization!r})"
        )

    def to_organization_member(self) -> OrganizationMember:
        return OrganizationMember.model_validate(self)


class OrganizationInviteOrm(TimestampMixin, Base):
    __tablename__ = "organization_invites"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, unique=True, nullable=False, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[OrgRole] = mapped_column(Enum(OrgRole), nullable=False)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    invited_by: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("users.id"), nullable=False
    )

    organization: Mapped["OrganizationOrm"] = relationship(back_populates="invites")

    def to_organization_invite(self) -> OrganizationInvite:
        return OrganizationInvite.model_validate(self)

    def __repr__(self) -> str:
        return (
            f"OrganizationInvite(id={self.id!r}, email={self.email!r}, "
            f"role={self.role!r}, organization={self.organization.id!r})"
        )

    @classmethod
    def to_invites_list(
        cls, invites: Sequence["OrganizationInviteOrm"]
    ) -> list[OrganizationInvite]:
        return [OrganizationInvite.model_validate(invite) for invite in invites]
