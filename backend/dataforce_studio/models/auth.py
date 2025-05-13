import uuid

from pydantic import BaseModel, EmailStr
from starlette.authentication import BaseUser


class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: str | None = None


class AuthUser(BaseUser):
    def __init__(
        self,
        user_id: uuid.UUID,
        email: EmailStr,
        full_name: str | None = None,
        disabled: bool | None = None,
    ) -> None:
        self.id = user_id
        self.email = email
        self.full_name = full_name
        self.disabled = disabled

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def display_name(self) -> EmailStr:
        return self.email
