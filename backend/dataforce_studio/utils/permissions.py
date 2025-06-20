from collections.abc import Sequence

from dataforce_studio.schemas.orbit import OrbitRole
from dataforce_studio.schemas.organization import OrgRole
from dataforce_studio.schemas.permissions import (
    Action,
    Resource,
    orbit_permissions,
    organization_permissions,
)


def get_organization_permissions_for_role_and_resources(
    role: OrgRole,
    resources: Sequence[Resource],
) -> dict[str, list[str]]:
    all_permissions = organization_permissions.get(role, {})

    result: dict[str, list[str]] = {}
    for resource in resources:
        if resource in all_permissions:
            result[str(resource.value)] = [
                action.value for action in all_permissions[resource]
            ]
    return result


def get_orbit_permissions_for_role_and_resources(
    role: OrbitRole,
    resources: Sequence[Resource],
) -> dict[str, list[str]]:
    all_permissions = orbit_permissions.get(role, {})

    result: dict[str, list[str]] = {}
    for resource in resources:
        if resource in all_permissions:
            result[str(resource.value)] = [
                action.value for action in all_permissions[resource]
            ]
    return result


def get_organization_permissions_by_role(role: str | OrgRole) -> dict[str, list[str]]:
    permissions = get_organization_permissions_for_role_and_resources(
        OrgRole(role),
        [
            Resource.ORGANIZATION,
            Resource.ORGANIZATION_USER,
            Resource.ORGANIZATION_INVITE,
            Resource.BILLING,
            Resource.ORBIT,
        ],
    )
    if Action.CREATE in permissions.get(Resource.ORBIT, []):
        permissions[Resource.ORBIT] = [Action.CREATE]
    else:
        permissions.pop(Resource.ORBIT, None)
    return permissions


def get_orbit_permissions_by_role(
    org_role: str | None, role: str | None
) -> dict[str, list[str]]:
    if org_role and org_role in (OrgRole.OWNER, OrgRole.ADMIN):
        return get_organization_permissions_for_role_and_resources(
            OrgRole(org_role),
            [Resource.ORBIT, Resource.ORBIT_USER, Resource.MODEL, Resource.COLLECTION],
        )

    if not role:
        return {}

    return get_orbit_permissions_for_role_and_resources(
        OrbitRole(role),
        [Resource.ORBIT, Resource.ORBIT_USER, Resource.MODEL, Resource.COLLECTION],
    )
