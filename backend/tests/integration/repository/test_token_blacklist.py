import time

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from dataforce_studio.repositories.token_blacklist import TokenBlackListRepository


@pytest.mark.asyncio
async def test_add_token(create_database_and_apply_migrations: str) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = TokenBlackListRepository(engine)

    token = "test-token-test_add_token"
    expire = int(time.time()) + 60

    await repo.add_token(token, expire)
    is_blacklisted = await repo.is_token_blacklisted(token)

    assert is_blacklisted is True


@pytest.mark.asyncio
async def test_is_token_blacklisted(create_database_and_apply_migrations: str) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = TokenBlackListRepository(engine)

    token = "test-token-test_is_token_blacklisted"
    expire = int(time.time()) - 60

    await repo.add_token(token, expire)
    is_blacklisted = await repo.is_token_blacklisted(token)

    assert is_blacklisted is False


@pytest.mark.asyncio
async def test_delete_expired_tokens(create_database_and_apply_migrations: str) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = TokenBlackListRepository(engine)

    token = "test-token-test_delete_expired_tokens"
    expire = int(time.time()) - 60
    for _ in range(3):
        await repo.add_token(token, expire)

    deleted = await repo.delete_expired_tokens()
    is_blacklisted = await repo.is_token_blacklisted(token)

    assert deleted is None
    assert is_blacklisted is False
