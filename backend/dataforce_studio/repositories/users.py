from pydantic import EmailStr
from sqlalchemy import select

from dataforce_studio.models.orm import UserOrm
from dataforce_studio.models.user import (
    UpdateUser,
    User,
)
from dataforce_studio.repositories.base import RepositoryBase


class UserRepository(RepositoryBase):
    async def create_user(
        self,
        user: User,
    ) -> User:
        async with self._get_session() as session:
            db_user = UserOrm.from_user(user)
            session.add(db_user)
            user = db_user.to_user()
            await session.commit()
        return user

    async def get_user(self, email: EmailStr) -> User | None:
        async with self._get_session() as session:
            result = await session.execute(
                select(UserOrm).filter(UserOrm.email == email)
            )
            db_user = result.scalar_one_or_none()
            return db_user.to_user() if db_user else None

    async def delete_user(self, email: EmailStr) -> None:
        async with self._get_session() as session:
            result = await session.execute(
                select(UserOrm).filter(UserOrm.email == email)
            )
            user = result.scalar_one_or_none()

            if user:
                await session.delete(user)
                await session.commit()

    async def update_user(
        self,
        update_user: UpdateUser,
    ) -> tuple[bool, User | None]:
        async with self._get_session() as session:
            changed = False
            result = await session.execute(
                select(UserOrm).filter(UserOrm.email == update_user.email)
            )

            if not (db_user := result.scalars().first()):
                return False, None

            fields_to_update = update_user.model_dump(exclude_unset=True)

            for field, value in fields_to_update.items():
                setattr(db_user, field, value)
                changed = True

        return changed, db_user.to_user()
