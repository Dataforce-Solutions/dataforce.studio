from typing import Literal

from pydantic import EmailStr, HttpUrl
from sqlalchemy import select

from dataforce_studio.models.auth import (
    AuthProvider,
    User as ServiceUser,
)
from dataforce_studio.models.orm import DBUser
from dataforce_studio.repositories.base import RepositoryBase


class UserRepository(RepositoryBase):
    async def create_user(
        self,
        email: EmailStr,
        full_name: str | None,
        disabled: bool,
        email_verified: bool,
        auth_method: AuthProvider,
        photo: str | None = None,
        hashed_password: str | None = None,
    ) -> ServiceUser:
        async with self._get_session() as session:
            db_user = DBUser(
                email=email,
                full_name=full_name,
                disabled=disabled,
                email_verified=email_verified,
                auth_method=auth_method,
                photo=photo,
                hashed_password=hashed_password,
            )
            session.add(db_user)
            user = db_user.to_service_user()
            await session.commit()
        return user

    async def get_user(self, email: str) -> ServiceUser | None:
        async with self._get_session() as session:
            result = await session.execute(select(DBUser).filter(DBUser.email == email))
            db_user = result.scalar_one_or_none()
            return db_user.to_service_user() if db_user else None

    async def delete_user(self, email: str) -> None:
        async with self._get_session() as session:
            result = await session.execute(select(DBUser).filter(DBUser.email == email))
            user = result.scalar_one_or_none()

            if user:
                await session.delete(user)
                await session.commit()

    async def update_user(
        self,
        email: str,
        full_name: str | None = None,
        disabled: bool | None = None,
        email_verified: bool | None = None,
        auth_provider: AuthProvider | None = None,
        photo: str | None = None,
        hashed_password: str | None | Literal["reset"] = None,
    ) -> ServiceUser | None:
        async with self._get_session() as session:
            result = await session.execute(select(DBUser).filter(DBUser.email == email))
            db_user = result.scalars().first()
            if db_user:
                if full_name:
                    db_user.full_name = full_name
                if disabled is not None:
                    db_user.disabled = disabled
                if email_verified is not None:
                    db_user.email_verified = email_verified
                if auth_provider:
                    db_user.auth_method = auth_provider
                if photo:
                    db_user.photo = HttpUrl(photo)
                if hashed_password:
                    if hashed_password == "reset":
                        db_user.hashed_password = None
                    else:
                        db_user.hashed_password = hashed_password
                user = db_user.to_service_user()
                await session.commit()
            return user
