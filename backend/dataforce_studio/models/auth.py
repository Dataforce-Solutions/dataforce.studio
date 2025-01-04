from enum import Enum
from typing import Literal

from pydantic import BaseModel, EmailStr, HttpUrl
from starlette.authentication import BaseUser


class AuthProvider(str, Enum):
    EMAIL = "EMAIL"
    GOOGLE = "GOOGLE"


class User(BaseModel):
    email: EmailStr
    full_name: str | None = None
    disabled: bool | None = None
    email_verified: bool = False
    auth_method: AuthProvider
    photo: HttpUrl | None = None


class ServiceUser(User):
    hashed_password: str | None | Literal["reset"] = None

    def to_user(self) -> User:
        return User(
            email=self.email,
            full_name=self.full_name,
            disabled=self.disabled,
            email_verified=self.email_verified,
            auth_method=self.auth_method,
            photo=self.photo,
        )


class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: str | None = None


class AuthUser(BaseUser):
    def __init__(
        self,
        email: str,
        full_name: str | None = None,
        disabled: bool | None = None,
    ) -> None:
        self.email = email
        self.full_name = full_name
        self.disabled = disabled

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def display_name(self) -> str:
        return self.email
