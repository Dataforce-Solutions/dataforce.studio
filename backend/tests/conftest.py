import asyncpg
import pytest_asyncio
from dataforce_studio.settings import config
from utils.db import migrate_db

TEST_DB_NAME = "df_studio_test"


async def _terminate_connections(conn, db_name: str) -> None:
    await conn.execute(
        """
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = $1 AND pid <> pg_backend_pid();
        """,
        db_name,
    )


async def _create_database(admin_dsn: str, db_name: str) -> None:
    conn = await asyncpg.connect(admin_dsn)
    await _terminate_connections(conn, db_name)
    await conn.execute(f'DROP DATABASE IF EXISTS "{db_name}";')
    await conn.execute(f'CREATE DATABASE "{db_name}";')
    await conn.close()


async def _drop_database(admin_dsn: str, db_name: str) -> None:
    conn = await asyncpg.connect(admin_dsn)
    await _terminate_connections(conn, db_name)
    await conn.execute(f'DROP DATABASE IF EXISTS "{db_name}";')
    await conn.close()


@pytest_asyncio.fixture(scope="function")
async def create_database_and_apply_migrations():  # noqa: ANN201
    admin_dsn = config.POSTGRESQL_DSN.replace("+asyncpg", "").replace(
        "df_studio", "postgres"
    )
    test_dsn = config.POSTGRESQL_DSN.replace("df_studio", TEST_DB_NAME)

    await _create_database(admin_dsn, TEST_DB_NAME)
    await migrate_db(test_dsn)

    yield test_dsn

    await _drop_database(admin_dsn, TEST_DB_NAME)
