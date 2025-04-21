import pytest
from models.auth import AuthProvider
from repositories.users import UserRepository
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.asyncio
async def test_create_user(create_database_and_apply_migrations) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = UserRepository(engine)
    email = "test@test.com"

    created_user = await repo.create_user(
        email=email,
        full_name="Test User",
        disabled=False,
        email_verified=True,
        auth_method=AuthProvider.EMAIL,
        photo=None,
        hashed_password="hashed_password",
    )

    fetched_user = await repo.get_user(email)

    assert created_user == fetched_user
