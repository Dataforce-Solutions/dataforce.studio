import pytest
import pytest_asyncio
from dataforce_studio.repositories.users import UserRepository
from dataforce_studio.schemas.user import UpdateUser, User, UserResponse
from sqlalchemy.ext.asyncio import create_async_engine


@pytest_asyncio.fixture(scope="function")
async def get_created_user(
    create_database_and_apply_migrations: str, test_user: dict
) -> dict:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = UserRepository(engine)

    user = await repo.create_user(User(**test_user))

    return {
        "engine": engine,
        "repo": repo,
        "user": user,
    }


@pytest.mark.asyncio
async def test_create_user(
    create_database_and_apply_migrations: str, test_user: dict
) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = UserRepository(engine)
    user = User(**test_user)

    created_user = await repo.create_user(user)

    fetched_user = await repo.get_user(user.email)

    assert created_user == fetched_user


@pytest.mark.asyncio
async def test_get_user(get_created_user: dict) -> None:
    data = get_created_user
    repo, user = data["repo"], data["user"]

    fetched_user = await repo.get_user(user.email)

    assert fetched_user
    assert isinstance(fetched_user, User)


@pytest.mark.asyncio
async def test_get_public_user(get_created_user: dict) -> None:
    data = get_created_user
    repo, user = data["repo"], data["user"]

    fetched_user = await repo.get_public_user(user.email)

    assert fetched_user
    assert isinstance(fetched_user, UserResponse)
    assert fetched_user.id
    assert fetched_user.email
    assert hasattr(fetched_user, "full_name")
    assert hasattr(fetched_user, "disabled")
    assert hasattr(fetched_user, "photo")
    assert not hasattr(fetched_user, "hashed_password")


@pytest.mark.asyncio
async def test_delete_user(get_created_user: dict) -> None:
    data = get_created_user
    repo, user = data["repo"], data["user"]

    deleted_user = await repo.delete_user(user.email)
    fetch_deleted_user = await repo.get_user(user.email)

    assert deleted_user is None
    assert fetch_deleted_user is None


@pytest.mark.asyncio
async def test_update_user(get_created_user: dict) -> None:
    data = get_created_user
    repo, user = data["repo"], data["user"]
    user_update_data = {"email": user.email, "email_verified": True}

    await repo.update_user(UpdateUser(**user_update_data))
    fetched_user = await repo.get_user(user.email)

    assert fetched_user.email == user_update_data["email"]
    assert fetched_user.email_verified == user_update_data["email_verified"]


@pytest.mark.asyncio
async def test_update_user_not_found(get_created_user: dict) -> None:
    data = get_created_user
    repo = data["repo"]
    user_update_data = {"email": "user_not_found@example.com", "email_verified": True}

    updated_user = await repo.update_user(UpdateUser(**user_update_data))

    assert updated_user is False
