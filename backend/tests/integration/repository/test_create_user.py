import pytest
from dataforce_studio.models.user import AuthProvider, User
from dataforce_studio.repositories.users import UserRepository
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.asyncio
async def test_create_user(create_database_and_apply_migrations) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = UserRepository(engine)
    user = User(
        email="test@email.com",
        full_name="Test User",
        disabled=False,
        email_verified=True,
        auth_method=AuthProvider.EMAIL,
        photo=None,
        hashed_password="hashed_password",
    )

    created_user = await repo.create_user(user)

    fetched_user = await repo.get_user(user.email)

    assert created_user == fetched_user
