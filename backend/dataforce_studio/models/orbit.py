import uuid

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dataforce_studio.models.base import Base, TimestampMixin
from dataforce_studio.models.organization import OrganizationOrm
from dataforce_studio.models.user import UserOrm
from dataforce_studio.schemas.orbit import Orbit, OrbitDetails, OrbitMember


class OrbitOrm(TimestampMixin, Base):
    __tablename__ = "orbits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(String, nullable=False)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )

    members: Mapped[list["OrbitMembersOrm"]] = relationship(
        back_populates="orbit", cascade="all, delete, delete-orphan"
    )

    organization: Mapped["OrganizationOrm"] = relationship(
        "OrganizationOrm",
        back_populates="orbits",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"Orbit(id={self.id!r})"

    def to_orbit(self) -> Orbit:
        return Orbit.model_validate(self)

    def to_orbit_details(self) -> OrbitDetails:
        return OrbitDetails.model_validate(self)


class OrbitMembersOrm(TimestampMixin, Base):
    __tablename__ = "orbit_members"
    __table_args__ = (UniqueConstraint("orbit_id", "user_id", name="orbit_member"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    orbit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("orbits.id", ondelete="CASCADE"), nullable=False
    )

    role: Mapped[str] = mapped_column(String, nullable=False)

    user: Mapped["UserOrm"] = relationship(
        "UserOrm", back_populates="orbit_memberships", lazy="selectin"
    )

    orbit: Mapped["OrbitOrm"] = relationship(
        "OrbitOrm", back_populates="members", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"OrbitMember(id={self.id!r}, user_id={self.user_id!r})"

    def to_orbit_member(self) -> OrbitMember:
        return OrbitMember.model_validate(self)
