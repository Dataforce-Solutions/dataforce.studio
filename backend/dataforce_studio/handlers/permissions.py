from dataforce_studio.infra.db import engine
from dataforce_studio.infra.exceptions import (
    InsufficientPermissionsError,
    NotFoundError,
)
from dataforce_studio.repositories.orbits import OrbitRepository
from dataforce_studio.repositories.users import UserRepository
from dataforce_studio.schemas.orbit import OrbitRole
from dataforce_studio.schemas.organization import OrgRole
from dataforce_studio.schemas.permissions import (
    Action,
    Resource,
    orbit_permissions,
    organization_permissions,
)


class PermissionsHandler:
    __user_repository = UserRepository(engine)
    __orbits_repository = OrbitRepository(engine)
    __org_permissions = organization_permissions
    __orbit_permissions = orbit_permissions

    def has_organization_permission(
        self, role: str, resource: Resource, action: Action
    ) -> bool:
        return action in self.__org_permissions.get(OrgRole(role), {}).get(resource, [])

    def has_orbit_permission(
        self, role: str, resource: Resource, action: Action
    ) -> bool:
        return action in self.__orbit_permissions.get(OrbitRole(role), {}).get(
            resource, []
        )

    async def check_organization_permission(
        self,
        organization_id: int,
        user_id: int,
        resource: Resource,
        action: Action,
    ) -> str:
        org_member_role = await self.__user_repository.get_organization_member_role(
            organization_id, user_id
        )

        if not org_member_role:
            raise NotFoundError("User is not member of the organization")

        if not self.has_organization_permission(org_member_role, resource, action):
            raise InsufficientPermissionsError()

        return org_member_role

    async def check_orbit_permission(
        self,
        orbit_id: int,
        user_id: int,
        resource: Resource,
        action: Action,
    ) -> str:
        member_role = await self.__orbits_repository.get_orbit_member_role(
            orbit_id, user_id
        )

        if not member_role:
            raise NotFoundError("User is not member of the orbit")

        if not self.has_orbit_permission(member_role, resource, action):
            raise InsufficientPermissionsError()

        return member_role

    async def check_orbit_action_access(
        self,
        organization_id: int,
        orbit_id: int,
        user_id: int,
        resource: Resource,
        action: Action,
    ) -> str | None:
        org_role = await self.check_organization_permission(
            organization_id,
            user_id,
            resource,
            action,
        )

        if org_role not in (OrgRole.OWNER, OrgRole.ADMIN):
            return await self.check_orbit_permission(
                orbit_id,
                user_id,
                resource,
                action,
            )

        return None
