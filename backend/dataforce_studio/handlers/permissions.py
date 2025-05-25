from dataforce_studio.infra.db import engine
from dataforce_studio.infra.exceptions import (
    InsufficientPermissionsError,
    NotFoundError,
)

from dataforce_studio.repositories.permissions import PermissionsRepository
from dataforce_studio.repositories.users import UserRepository
from dataforce_studio.schemas.permissions import (
    OrgPermission,
    OrbitPermission,
    Resources,
    ResourceAction,
)


class PermissionsHandler:
    __user_repository = UserRepository(engine)
    __permissions_repository = PermissionsRepository(engine)

    async def check_organization_permission(
        self,
        organization_id: int,
        user_id: int,
        resource: Resources,
        action: ResourceAction,
    ):
        org_member_role = await self.__user_repository.get_organization_member_role(
            organization_id, user_id
        )

        if not org_member_role:
            raise NotFoundError("User is not member of the organization")

        permission = await self.__permissions_repository.get_organization_permission(
            OrgPermission(role=org_member_role, resource=resource, action=action)
        )
        if not permission:
            raise InsufficientPermissionsError()
