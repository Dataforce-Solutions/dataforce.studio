import pytest
from dataforce_studio.repositories.users import UserRepository
from sqlalchemy.ext.asyncio import create_async_engine

from dataforce_studio.schemas.user import User, AuthProvider


@pytest.mark.asyncio
async def test_get_public_user(create_database_and_apply_migrations: str, test_user) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = UserRepository(engine)
    user = User(**test_user)

    await repo.create_user(user)

    fetched_user = await repo.get_public_user(user.email)

    assert fetched_user
    assert fetched_user.id
    assert fetched_user.email
    assert hasattr(fetched_user, "full_name")
    assert hasattr(fetched_user, "disabled")
    assert hasattr(fetched_user, "photo")
    assert not hasattr(fetched_user, "hashed_password")
