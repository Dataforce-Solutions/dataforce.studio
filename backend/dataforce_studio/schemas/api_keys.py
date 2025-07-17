from pydantic import BaseModel

from dataforce_studio.schemas.base import BaseOrmConfig
from dataforce_studio.schemas.user import UserOut


class APIKeyCreate(BaseModel):
    user_id: int
    hash: str


class APIKeyOut(BaseModel, BaseOrmConfig):
    id: int
    user_id: int


class APIKeyCreateOut(APIKeyOut):
    key: str


class APIKeyAuthOut(APIKeyOut):
    user: UserOut
