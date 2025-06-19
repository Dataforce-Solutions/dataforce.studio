from collections.abc import Sequence
from typing import Any, TypeVar

from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from dataforce_studio.models.base import Base

TOrm = TypeVar("TOrm", bound=Base)
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

    async def create_models(
        self,
        session: AsyncSession,
        orm_class: type,
        data_list: list[TPydantic],
    ) -> list:
        db_objects = [orm_class(**item.model_dump()) for item in data_list]
        session.add_all(db_objects)
        await session.flush()
        await session.commit()
        for obj in db_objects:
            await session.refresh(obj)
        return db_objects

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

    async def delete_model_where(
        self, session: AsyncSession, orm_class: type[TOrm], *where_conditions
    ) -> None:
        result = await session.execute(select(orm_class).where(*where_conditions))  # type: ignore[attr-defined]
        obj = result.scalar_one_or_none()

        if obj:
            await session.delete(obj)
            await session.commit()

    async def delete_models_where(
        self, session: AsyncSession, orm_class: type[TOrm], *where_conditions
    ) -> None:
        await session.execute(delete(orm_class).where(*where_conditions))  # type: ignore[attr-defined]
        await session.commit()

    async def get_model_where(
        self,
        session: AsyncSession,
        orm_class: type[TOrm],
        *where_conditions,
        options: list | None = None,
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
        options: list | None = None,
        use_unique: bool = False,
    ) -> TOrm | None:
        result = await session.execute(
            select(orm_class)
            .where(orm_class.id == obj_id)  # type: ignore[attr-defined]
            .options(*(options or []))
        )

        if use_unique:
            return result.unique().scalar_one_or_none()
        return result.scalar_one_or_none()

    async def get_models_where(
        self,
        session: AsyncSession,
        orm_class: type[TOrm],
        *where_conditions,
        options: list | None = None,
        order_by: list | None = None,
        join_condition: tuple | None = None,  # type: ignore[ANN401]
        select_fields: list | None = None,
        use_unique: bool = False,
    ) -> Sequence[Any]:
        stmt = select(*(select_fields or [orm_class]))

        if join_condition:
            stmt = stmt.join(*join_condition)

        stmt = (
            stmt.where(*where_conditions)
            .options(*(options or []))  # type: ignore[attr-defined]
            .order_by(*(order_by or []))
        )

        result = await session.execute(stmt)

        if use_unique:
            return result.unique().all()
        return result.scalars().all()

    async def get_model_count(
        self,
        session: AsyncSession,
        orm_class: type[TOrm],
        *where_conditions,
    ) -> int:
        result = await session.execute(
            select(func.count()).select_from(orm_class).where(*where_conditions)  # type: ignore[attr-defined]
        )
        return result.scalar() or 0
