from pydantic import EmailStr, HttpUrl
from sqlalchemy import Boolean, Enum, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from dataforce_studio.models.auth import (
    AuthProvider,
    ServiceUser,
)


class Base(DeclarativeBase):
    pass


class DBUser(Base):
    __tablename__ = "users"

    email: Mapped[EmailStr] = mapped_column(
        String, primary_key=True, unique=True, nullable=False
    )
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

    def to_service_user(self) -> ServiceUser:
        return ServiceUser(
            email=self.email,
            full_name=self.full_name,
            disabled=self.disabled,
            email_verified=self.email_verified,
            auth_method=self.auth_method,
            photo=self.photo,
            hashed_password=self.hashed_password,
        )


class TokenBlackList(Base):
    __tablename__ = "token_black_list"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String, nullable=False)
    expire_at: Mapped[int] = mapped_column(Integer, nullable=False)
