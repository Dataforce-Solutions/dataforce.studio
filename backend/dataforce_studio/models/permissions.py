from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dataforce_studio.models.base import Base, TimestampMixin
from dataforce_studio.schemas.orbit import OrbitRole
from dataforce_studio.schemas.permissions import Resources, ResourceAction


class OrganizationRolePermissionsOrm(TimestampMixin, Base):
    __tablename__ = "organization_role_permissions"
    __table_args__ = (
        UniqueConstraint("role", "resource", "action", name="uq_org_perm"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role: Mapped[OrbitRole] = mapped_column(String, nullable=False)
    resource: Mapped[Resources] = mapped_column(String, nullable=False)
    action: Mapped[ResourceAction] = mapped_column(String, nullable=False)

    def __repr__(self) -> str:
        return f"OrganizationRolePermissionsOrm(role={self.role!r}, resource={self.resource!r}, action={self.action!r})"


class OrbitRolePermissionsOrm(TimestampMixin, Base):
    __tablename__ = "orbit_role_permissions"
    __table_args__ = (
        UniqueConstraint("role", "resource", "action", name="uq_orbit_perm"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role: Mapped[OrbitRole] = mapped_column(String, nullable=False)
    resource: Mapped[Resources] = mapped_column(String, nullable=False)
    action: Mapped[ResourceAction] = mapped_column(String, nullable=False)

    def __repr__(self) -> str:
        return f"OrbitRolePermissionsOrm(role={self.role!r}, resource={self.resource!r}, action={self.action!r})"
