from sqlalchemy.ext.asyncio import create_async_engine

from dataforce_studio.settings import config

engine = create_async_engine(config.POSTGRESQL_DSN)
