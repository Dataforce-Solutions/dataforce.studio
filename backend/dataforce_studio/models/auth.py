from enum import Enum

from pydantic import BaseModel, EmailStr
from pydantic_core._pydantic_core import Url
from starlette.authentication import BaseUser


class AuthProvider(str, Enum):
    EMAIL = "email"
    GOOGLE = "google"


class User(BaseModel):
    email: EmailStr
    full_name: str | None = None
    disabled: bool | None = None
    email_verified: bool = False
    auth_method: AuthProvider
    photo: Url = Url(
        "https://previews.123rf.com/images/vectorshots/vectorshots1309/vectorshots130901404/22318678-cute-boy-cartoon-face-vector.jpg"
    )


class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: str | None = None


class UserInDB(User):
    hashed_password: str | None


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
