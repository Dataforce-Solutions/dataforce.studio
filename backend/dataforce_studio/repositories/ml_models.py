from sqlalchemy import func, select

from dataforce_studio.models import MLModelOrm
from dataforce_studio.repositories.base import CrudMixin, RepositoryBase
from dataforce_studio.schemas.ml_models import (
    MLModel,
    MLModelCreate,
    MLModelStatus,
    MLModelUpdate,
)


class MLModelRepository(RepositoryBase, CrudMixin):
    async def create_ml_model(self, model: MLModelCreate) -> MLModel:
        async with self._get_session() as session:
            db_model = await self.create_model(session, MLModelOrm, model)
            return db_model.to_ml_model()

    async def confirm_upload(self, model_id: int) -> MLModel | None:
        async with self._get_session() as session:
            db_model = await self.update_model_where(
                session,
                MLModelOrm,
                MLModelUpdate(id=model_id, status=MLModelStatus.UPLOADED),
                MLModelOrm.id == model_id,
            )
            return db_model.to_ml_model() if db_model else None

    async def update_status(
        self, model_id: int, status: MLModelStatus
    ) -> MLModel | None:
        async with self._get_session() as session:
            db_model = await self.update_model_where(
                session,
                MLModelOrm,
                MLModelUpdate(id=model_id, status=status),
                MLModelOrm.id == model_id,
            )
            return db_model.to_ml_model() if db_model else None

    async def delete_ml_model(self, model_id: int) -> None:
        async with self._get_session() as session:
            await self.delete_model(session, MLModelOrm, model_id)

    async def get_collection_models(
        self, collection_id: int, uploaded_only: bool = True
    ) -> list[MLModel]:
        async with self._get_session() as session:
            conditions = [MLModelOrm.collection_id == collection_id]
            if uploaded_only:
                conditions.append(
                    MLModelOrm.status.in_(
                        [
                            MLModelStatus.UPLOADED.value,
                            MLModelStatus.PENDING_DELETION.value,
                        ]
                    )
                )
            result = await session.execute(select(MLModelOrm).where(*conditions))
            db_versions = result.scalars().all()
            return [v.to_ml_model() for v in db_versions]

    async def get_ml_model(self, model_id: int) -> MLModel | None:
        async with self._get_session() as session:
            db_model = await self.get_model(session, MLModelOrm, model_id)
            return db_model.to_ml_model() if db_model else None

    async def update_ml_model(
        self, model_id: int, model: MLModelUpdate
    ) -> MLModel | None:
        model.id = model_id
        async with self._get_session() as session:
            db_model = await self.update_model(
                session=session, orm_class=MLModelOrm, data=model
            )
            return db_model.to_ml_model() if db_model else None

    async def get_collection_models_count(self, collection_id: int) -> int:
        async with self._get_session() as session:
            result = await session.execute(
                select(func.count())
                .select_from(MLModelOrm)
                .where(MLModelOrm.collection_id == collection_id)
            )
            return result.scalar() or 0
