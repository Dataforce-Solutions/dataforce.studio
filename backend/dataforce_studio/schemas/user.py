from enum import Enum

from pydantic import BaseModel, EmailStr

from dataforce_studio.schemas.base import BaseOrmConfig


class AuthProvider(str, Enum):
    EMAIL = "EMAIL"
    GOOGLE = "GOOGLE"


class _UserBase(BaseModel):
    id: int | None = None
    email: EmailStr
    full_name: str | None = None
    disabled: bool | None = None
    email_verified: bool = False
    auth_method: AuthProvider
    photo: str | None = None
    hashed_password: str | None = None


class CreateUser(_UserBase): ...


class User(_UserBase, BaseOrmConfig):
    id: int


class UserOut(BaseModel, BaseOrmConfig):
    id: int
    email: EmailStr
    full_name: str | None = None
    disabled: bool | None = None
    photo: str | None = None


class CreateUserIn(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None
    photo: str | None = None


class UpdateUserIn(BaseModel):
    password: str | None = None
    full_name: str | None = None
    disabled: bool | None = None
    auth_method: AuthProvider | None = None
    photo: str | None = None


class UpdateUser(UpdateUserIn):
    email: EmailStr
    email_verified: bool | None = None
    hashed_password: str | None = None
