from enum import Enum

from pydantic import BaseModel, EmailStr, field_validator

from dataforce_studio.models.auth import Token
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

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        if isinstance(value, str):
            return value.lower().strip()
        return value

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str | None) -> str | None:
        if not value:
            return value
        return " ".join(value.strip().split())


class SignInUser(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        if isinstance(value, str):
            return value.lower().strip()
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return value


class SignInResponse(BaseModel):
    token: Token
    user_id: int


class UpdateUserIn(BaseModel):
    password: str | None = None
    full_name: str | None = None
    disabled: bool | None = None
    auth_method: AuthProvider | None = None
    photo: str | None = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str | None) -> str | None:
        if value is None:
            return value

        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return value

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return " ".join(value.strip().split())


class UpdateUser(UpdateUserIn):
    email: EmailStr
    email_verified: bool | None = None
    hashed_password: str | None = None
