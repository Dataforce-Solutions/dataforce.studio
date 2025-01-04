from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine


class RepositoryBase:
    _engine: AsyncEngine | None = None

    @classmethod
    def get_engine(cls: "RepositoryBase") -> AsyncEngine:
        if cls._engine is None:
            cls._engine = cls._create_engine()
        return cls._engine

    @staticmethod
    def _create_engine() -> AsyncEngine:
        return create_async_engine(
            "postgresql+asyncpg://dfs:DbivVBCZr64aD18FEgAn@164.92.171.217:5432/df_studio"
        )

    def _get_session(self) -> AsyncSession:
        return AsyncSession(self.get_engine(), expire_on_commit=True)
