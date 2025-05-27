from collections.abc import Sequence
from typing import TypeVar

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

TOrm = TypeVar("TOrm")
TPydantic = TypeVar("TPydantic", bound=BaseModel)


class RepositoryBase:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    def _get_session(self) -> AsyncSession:
        return AsyncSession(self._engine, expire_on_commit=True)


class CrudMixin:
    async def create_model(
        self, session: AsyncSession, orm_class: type[TOrm], data: TPydantic
    ) -> TOrm:
        db_obj = orm_class(**data.model_dump())
        session.add(db_obj)
        await session.commit()
        await session.refresh(db_obj)
        return db_obj

    async def update_model_where(
        self,
        session: AsyncSession,
        orm_class: type[TOrm],
        data: TPydantic,
        *where_conditions,
    ) -> TOrm | None:
        result = await session.execute(select(orm_class).where(*where_conditions))
        db_obj = result.scalar_one_or_none()

        if not db_obj:
            return None

        fields_to_update = data.model_dump(exclude_unset=True)
        if not fields_to_update:
            return db_obj

        for field, value in fields_to_update.items():
            setattr(db_obj, field, value)

        await session.commit()
        await session.refresh(db_obj)

        return db_obj

    async def update_model(
        self,
        session: AsyncSession,
        orm_class: type[TOrm],
        data: TPydantic,
    ) -> TOrm | None:
        return await self.update_model_where(
            session,
            orm_class,
            data,
            orm_class.id == data.id,  # type: ignore[attr-defined]
        )

    async def delete_model(
        self,
        session: AsyncSession,
        orm_class: type[TOrm],
        obj_id: int,
    ) -> None:
        result = await session.execute(select(orm_class).where(orm_class.id == obj_id))  # type: ignore[attr-defined]
        db_obj = result.scalar_one_or_none()
        if db_obj:
            await session.delete(db_obj)
            await session.commit()

    async def get_model_where(
        self,
        session: AsyncSession,
        orm_class: type[TOrm],
        *where_conditions,
        options: list = None,
    ) -> TOrm | None:
        result = await session.execute(
            select(orm_class)
            .where(*where_conditions)  # type: ignore[attr-defined]
            .options(*(options or []))
        )

        return result.scalar_one_or_none()

    async def get_model(
        self,
        session: AsyncSession,
        orm_class: type[TOrm],
        obj_id: int,
        options: list = None,
    ) -> TOrm | None:
        result = await session.execute(
            select(orm_class)
            .where(orm_class.id == obj_id)  # type: ignore[attr-defined]
            .options(*(options or []))
        )

        return result.scalar_one_or_none()

    async def get_models_where(
        self,
        session: AsyncSession,
        orm_class: type[TOrm],
        *where_conditions,
        options: list = None,
        order_by: list | None = None,
    ) -> Sequence[TOrm]:
        result = await session.execute(
            select(orm_class)
            .where(*where_conditions)  # type: ignore[attr-defined]
            .options(*(options or []))
            .order_by(*(order_by or []))
        )
        return result.scalars().all()
