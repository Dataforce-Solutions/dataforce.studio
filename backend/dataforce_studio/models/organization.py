from collections.abc import Sequence

from pydantic import EmailStr
from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dataforce_studio.models.base import Base, TimestampMixin
from dataforce_studio.models.bucket_secrets import BucketSecretOrm
from dataforce_studio.schemas.organization import (
    Organization,
    OrganizationDetails,
    OrganizationInvite,
    OrganizationMember,
    UserInvite,
)


class OrganizationOrm(TimestampMixin, Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    name: Mapped[str | None] = mapped_column(String, nullable=False)
    logo: Mapped[str | None] = mapped_column(String, nullable=True)
    default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    members: Mapped[list["OrganizationMemberOrm"]] = relationship(
        back_populates="organization", cascade="all, delete, delete-orphan"
    )

    invites: Mapped[list["OrganizationInviteOrm"]] = relationship(
        back_populates="organization", cascade="all, delete, delete-orphan"
    )

    orbits: Mapped[list["OrbitOrm"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="organization", cascade="all, delete, delete-orphan"
    )

    bucket_secrets: Mapped[list["BucketSecretOrm"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="organization", cascade="all, delete, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"Organization(id={self.id!r}, name={self.name!r})"

    def to_organization(self) -> Organization:
        return Organization.model_validate(self)

    def to_organization_details(self) -> OrganizationDetails:
        return OrganizationDetails.model_validate(self)


class OrganizationMemberOrm(TimestampMixin, Base):
    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="org_member"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )

    role: Mapped[str] = mapped_column(String, nullable=False)

    user: Mapped["UserOrm"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "UserOrm", back_populates="memberships", lazy="selectin"
    )
    organization: Mapped["OrganizationOrm"] = relationship(back_populates="members")

    def __repr__(self) -> str:
        return f"OrganizationMember(id={self.id!r}, user_id={self.user_id!r})"

    def to_organization_member(self) -> OrganizationMember:
        return OrganizationMember.model_validate(self)


class OrganizationInviteOrm(TimestampMixin, Base):
    __tablename__ = "organization_invites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[EmailStr] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    invited_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    organization: Mapped["OrganizationOrm"] = relationship(back_populates="invites")

    invited_by_user: Mapped["UserOrm"] = relationship("UserOrm", lazy="selectin")  # type: ignore[name-defined]  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"OrganizationInvite(id={self.id!r}, email={self.email!r}, "
            f"role={self.role!r})"
        )

    @classmethod
    def to_invites_list(
        cls, invites: Sequence["OrganizationInviteOrm"]
    ) -> list[OrganizationInvite]:
        return [OrganizationInvite.model_validate(invite) for invite in invites]

    @classmethod
    def to_user_invites_list(
        cls, invites: Sequence["OrganizationInviteOrm"]
    ) -> list[UserInvite]:
        return [UserInvite.model_validate(invite) for invite in invites]

    def to_organization_invite(self) -> OrganizationInvite:
        return OrganizationInvite.model_validate(self)
