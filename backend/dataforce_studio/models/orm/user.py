import uuid

from pydantic import EmailStr, HttpUrl
from sqlalchemy import Boolean, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Boolean, Enum, String, Integer
from sqlalchemy.orm import Mapped, mapped_column

from dataforce_studio.models.base import Base, TimestampMixin
from dataforce_studio.models.user import AuthProvider, User, UserResponse
from dataforce_studio.models.orm.base import Base, TimestampMixin
from dataforce_studio.models.user import AuthProvider, CreateUser, User


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

    def to_user(self) -> User:
        return User.model_validate(self)

    @classmethod
    def from_user(cls, user: CreateUser) -> "UserOrm":
        return UserOrm(
            **user.model_dump(),
        )


class TokenBlackListOrm(Base):
    __tablename__ = "token_black_list"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String, nullable=False)
    expire_at: Mapped[int] = mapped_column(Integer, nullable=False)
