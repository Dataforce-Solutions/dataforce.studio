from enum import StrEnum

from pydantic import BaseModel

from dataforce_studio.schemas.base import BaseOrmConfig
from dataforce_studio.schemas.orbit import OrbitRole
from dataforce_studio.schemas.organization import OrgRole


class Resources(StrEnum):
    ORGANIZATION = "organization"
    ORGANIZATION_USER = "organization_user"
    ORGANIZATION_INVITE = "organization_invite"
    ORBIT = "orbit"
    ORBIT_USER = "orbit_user"
    BILLING = "billing"
    MODEL = "model"


class ResourceAction(StrEnum):
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
    resource: Resources
    action: ResourceAction


class OrbitPermission(BaseModel, BaseOrmConfig):
    role: OrbitRole | str
    resource: Resources
    action: ResourceAction


class OrgPermissionOut(OrgPermission):
    id: int


class OrbitPermissionOut(OrbitPermission):
    id: int
