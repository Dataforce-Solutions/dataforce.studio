from enum import StrEnum

from pydantic import BaseModel

from dataforce_studio.schemas.base import BaseOrmConfig
from dataforce_studio.schemas.orbit import OrbitRole
from dataforce_studio.schemas.organization import OrgRole


class Resource(StrEnum):
    ORGANIZATION = "organization"
    ORGANIZATION_USER = "organization_user"
    ORGANIZATION_INVITE = "organization_invite"
    ORBIT = "orbit"
    ORBIT_USER = "orbit_user"
    BILLING = "billing"
    BUCKET_SECRET = "bucket_secret"
    MODEL = "model"


class Action(StrEnum):
    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    LIST = "list"
    LEAVE = "leave"
    DEPLOY = "deploy"
    ACCEPT = "accept"
    REJECT = "reject"


class OrgPermission(BaseModel, BaseOrmConfig):
    role: OrgRole | str
    resource: Resource
    action: Action


class OrbitPermission(BaseModel, BaseOrmConfig):
    role: OrbitRole | str
    resource: Resource
    action: Action


class OrgPermissionOut(OrgPermission):
    id: int


class OrbitPermissionOut(OrbitPermission):
    id: int


organization_permissions = {
    OrgRole.OWNER: {
        Resource.ORGANIZATION: [Action.READ, Action.UPDATE, Action.DELETE],
        Resource.ORGANIZATION_USER: [
            Action.LIST,
            Action.READ,
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
        ],
        Resource.ORGANIZATION_INVITE: [
            Action.CREATE,
            Action.DELETE,
            Action.LIST,
            Action.ACCEPT,
            Action.REJECT,
            Action.READ,
        ],
        Resource.ORBIT: [
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
            Action.LIST,
            Action.READ,
        ],
        Resource.ORBIT_USER: [
            Action.LIST,
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
            Action.READ,
        ],
        Resource.BUCKET_SECRET: [
            Action.LIST,
            Action.READ,
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
        ],
        Resource.MODEL: [
            Action.LIST,
            Action.READ,
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
            Action.DEPLOY,
        ],
        Resource.BILLING: [Action.READ, Action.UPDATE],
    },
    OrgRole.ADMIN: {
        Resource.ORGANIZATION: [Action.READ, Action.UPDATE, Action.LEAVE],
        Resource.ORGANIZATION_USER: [
            Action.LIST,
            Action.READ,
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
        ],
        Resource.ORGANIZATION_INVITE: [
            Action.CREATE,
            Action.DELETE,
            Action.LIST,
            Action.ACCEPT,
            Action.REJECT,
            Action.READ,
        ],
        Resource.ORBIT: [Action.CREATE, Action.UPDATE, Action.LIST, Action.READ],
        Resource.ORBIT_USER: [
            Action.LIST,
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
            Action.READ,
        ],
        Resource.BUCKET_SECRET: [
            Action.LIST,
            Action.READ,
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
        ],
        Resource.MODEL: [
            Action.LIST,
            Action.READ,
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
            Action.DEPLOY,
        ],
    },
    OrgRole.MEMBER: {
        Resource.ORGANIZATION: [Action.READ, Action.LEAVE],
        Resource.ORGANIZATION_INVITE: [Action.ACCEPT, Action.REJECT],
        Resource.ORBIT: [Action.LIST, Action.READ],
    },
}

orbit_permissions = {
    OrbitRole.ADMIN: {
        Resource.ORBIT: [
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
            Action.LIST,
            Action.READ,
        ],
        Resource.ORBIT_USER: [
            Action.LIST,
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
            Action.READ,
        ],
        Resource.MODEL: [
            Action.LIST,
            Action.READ,
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
            Action.DEPLOY,
        ],
    },
    OrbitRole.MEMBER: {
        Resource.ORBIT: [Action.LIST, Action.READ],
        Resource.MODEL: [
            Action.LIST,
            Action.READ,
            Action.CREATE,
            Action.UPDATE,
            Action.DEPLOY,
        ],
    },
}
