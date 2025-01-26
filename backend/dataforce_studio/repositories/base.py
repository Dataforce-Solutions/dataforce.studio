from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from dataforce_studio.settings import config


class RepositoryBase:
    _engine: AsyncEngine | None = None

    @classmethod
    def get_engine(cls: "RepositoryBase") -> AsyncEngine:
        if cls._engine is None:
            cls._engine = cls._create_engine()
        return cls._engine

    @staticmethod
    def _create_engine() -> AsyncEngine:
        return create_async_engine(config.POSTGRESQL_DSN)

    def _get_session(self) -> AsyncSession:
        return AsyncSession(self.get_engine(), expire_on_commit=True)
