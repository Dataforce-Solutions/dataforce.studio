import uuid

from pydantic import EmailStr, HttpUrl
from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from dataforce_studio.models.base import Base, TimestampMixin
from dataforce_studio.models.user import AuthProvider, CreateUser, UserResponse


class UserOrm(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, unique=True, nullable=False, default=uuid.uuid4
    )
    email: Mapped[EmailStr] = mapped_column(String, unique=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    auth_method: Mapped[AuthProvider] = mapped_column(
        Enum(AuthProvider), nullable=False
    )
    photo: Mapped[HttpUrl | None] = mapped_column(String, nullable=True)
    hashed_password: Mapped[str | None] = mapped_column(String, nullable=True)

    def __repr__(self) -> str:
        return f"User(email={self.email!r}, full_name={self.full_name!r}"

    def to_user(self) -> UserResponse:
        return UserResponse.model_validate(self.__dict__)

    @classmethod
    def from_user(cls, user: CreateUser) -> "UserOrm":
        return UserOrm(
            **user.model_dump(),
        )
