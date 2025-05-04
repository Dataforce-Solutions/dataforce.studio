from enum import Enum

from pydantic import BaseModel, EmailStr, HttpUrl

from dataforce_studio.models.base import BaseOrmConfig


class AuthProvider(str, Enum):
    EMAIL = "EMAIL"
    GOOGLE = "GOOGLE"


class _UserBase(BaseModel):
    email: EmailStr
    full_name: str | None = None
    disabled: bool | None = None
    email_verified: bool = False
    auth_method: AuthProvider
    photo: HttpUrl | None = None
    hashed_password: str | None = None


class User(_UserBase, BaseOrmConfig): ...


class CreateUserIn(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None
    photo: HttpUrl | None = None


class UpdateUserIn(BaseModel):
    hashed_password: str | None = None
    full_name: str | None = None
    disabled: bool | None = None
    auth_method: AuthProvider | None = None
    photo: HttpUrl | None = None


class UpdateUser(UpdateUserIn):
    email: EmailStr
    email_verified: bool | None = None
