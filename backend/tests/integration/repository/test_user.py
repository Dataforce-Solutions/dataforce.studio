import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from dataforce_studio.repositories.users import UserRepository
from dataforce_studio.schemas.user import (
    AuthProvider,
    CreateUser,
    UpdateUser,
    User,
    UserOut,
)


@pytest.mark.asyncio
async def test_create_user_automatically_creates_default_organization(
    create_database_and_apply_migrations: str,
) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = UserRepository(engine)

    create_user_data = CreateUser(
        email="test@email.com",
        full_name="Test User",
        disabled=False,
        email_verified=True,
        auth_method=AuthProvider.EMAIL,
        photo=None,
        hashed_password="hashed_password",
    )

    created_user = await repo.create_user(create_user_data)

    assert created_user is not None
    assert created_user.email == create_user_data.email
    assert created_user.full_name == create_user_data.full_name

    fetched_user = await repo.get_user(create_user_data.email)
    assert fetched_user == created_user

    user_organizations = await repo.get_user_organizations(created_user.id)
    assert len(user_organizations) == 1

    default_org = user_organizations[0]
    assert default_org.name == "Test's organization"

    org_members = await repo.get_organization_users(default_org.id)
    assert len(org_members) >= 1, "Organization should have at least one member"


@pytest.mark.asyncio
async def test_get_user(create_database_and_apply_migrations: str) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = UserRepository(engine)

    create_user = CreateUser(
        email="testcreateorganization@example.com",
        full_name="Test User",
        disabled=False,
        email_verified=True,
        auth_method=AuthProvider.EMAIL,
        photo=None,
        hashed_password="hashed_password",
    )

    user = await repo.create_user(create_user)
    fetched_user = await repo.get_user(user.email)

    assert fetched_user
    assert isinstance(fetched_user, User)


@pytest.mark.asyncio
async def test_get_public_user(create_database_and_apply_migrations: str) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = UserRepository(engine)

    create_user_data = CreateUser(
        email="public.user@example.com",
        full_name="Public Test User",
        disabled=False,
        email_verified=True,
        auth_method=AuthProvider.EMAIL,
        photo="https://example.com/photo.jpg",
        hashed_password="super_secret_hashed_password",
    )

    created_user = await repo.create_user(create_user_data)
    public_user = await repo.get_public_user(created_user.email)

    assert public_user is not None
    assert isinstance(public_user, UserOut)

    assert public_user.id == created_user.id
    assert public_user.email == create_user_data.email
    assert public_user.full_name == create_user_data.full_name
    assert public_user.disabled == create_user_data.disabled
    assert public_user.photo == create_user_data.photo

    assert not hasattr(public_user, "hashed_password")


@pytest.mark.asyncio
async def test_delete_user(create_database_and_apply_migrations: str) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = UserRepository(engine)

    create_user = CreateUser(
        email="testcreateorganization@example.com",
        full_name="Test User",
        disabled=False,
        email_verified=True,
        auth_method=AuthProvider.EMAIL,
        photo=None,
        hashed_password="hashed_password",
    )

    user = await repo.create_user(create_user)
    deleted_user = await repo.delete_user(user.email)
    fetch_deleted_user = await repo.get_user(user.email)

    assert deleted_user is None
    assert fetch_deleted_user is None


@pytest.mark.asyncio
async def test_update_user(create_database_and_apply_migrations: str) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = UserRepository(engine)

    create_user = CreateUser(
        email="testcreateorganization@example.com",
        full_name="Test User",
        disabled=False,
        email_verified=False,
        auth_method=AuthProvider.EMAIL,
        photo=None,
        hashed_password="hashed_password",
    )

    user = await repo.create_user(create_user)
    user_update_data = UpdateUser(email=user.email, email_verified=True)

    await repo.update_user(user_update_data)
    fetched_user = await repo.get_user(user.email)

    assert fetched_user.email == user_update_data.email
    assert fetched_user.email_verified == user_update_data.email_verified


@pytest.mark.asyncio
async def test_update_user_not_found(create_database_and_apply_migrations: str) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = UserRepository(engine)

    user_update_data = UpdateUser(
        email="user_not_found@example.com", email_verified=True
    )

    updated_user = await repo.update_user(user_update_data)

    assert updated_user is False, "Updating non-existent user should return False"
