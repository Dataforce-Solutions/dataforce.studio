import random

import asyncpg
import pytest_asyncio
from dataforce_studio.repositories.bucket_secrets import BucketSecretRepository
from dataforce_studio.repositories.invites import InviteRepository
from dataforce_studio.repositories.orbits import OrbitRepository
from dataforce_studio.repositories.users import UserRepository
from dataforce_studio.schemas.bucket_secrets import BucketSecretCreate
from dataforce_studio.schemas.orbit import (
    OrbitMemberCreate,
    OrbitRole,
    OrbitCreateIn,
)
from dataforce_studio.schemas.organization import (
    CreateOrganizationInvite,
    OrgRole,
    OrganizationMemberCreate,
    OrganizationCreateIn,
)
from dataforce_studio.schemas.user import AuthProvider, CreateUser
from dataforce_studio.settings import config
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from utils.db import migrate_db

TEST_DB_NAME = "df_studio_test"


async def _terminate_connections(conn: AsyncConnection, db_name: str) -> None:
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


@pytest_asyncio.fixture(scope="function")
def test_user() -> dict:
    return {
        "email": "testuser@example.com",
        "full_name": "Test User",
        "disabled": False,
        "email_verified": True,
        "auth_method": AuthProvider.EMAIL,
        "photo": None,
        "hashed_password": "hashed_password",
    }


@pytest_asyncio.fixture(scope="function")
async def create_organization_with_user(
    create_database_and_apply_migrations: str, test_user: dict
) -> dict:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = UserRepository(engine)
    secret_repo = BucketSecretRepository(engine)

    user = await repo.create_user(CreateUser(**test_user))

    created_organization = await repo.create_organization(
        user.id, OrganizationCreateIn(name="test org")
    )
    member = await repo.get_organization_member(created_organization.id, user.id)

    secret = await secret_repo.create_bucket_secret(
        BucketSecretCreate(
            organization_id=created_organization.id,
            endpoint="s3",
            bucket_name="test-bucket",
        )
    )

    return {
        "engine": engine,
        "repo": repo,
        "user": user,
        "organization": created_organization,
        "bucket_secret": secret,
        "member": member,
    }


@pytest_asyncio.fixture(scope="function")
async def create_organization_with_members(
    create_database_and_apply_migrations: str,
) -> dict:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = UserRepository(engine)
    invites_repo = InviteRepository(engine)
    members, users, invites = [], [], []

    user_main = await repo.create_user(
        CreateUser(
            email="userMAIN@gmail.com",
            full_name="Test User MAIN",
            disabled=False,
            email_verified=True,
            auth_method=AuthProvider.EMAIL,
            photo=None,
            hashed_password="hashed_password",
        )
    )

    users.append(user_main)

    organization = await repo.create_organization(
        user_main.id, OrganizationCreateIn(name="Test org with members")
    )
    owner = await repo.get_organization_member(organization.id, user_main.id)
    members.append(owner)

    for i in range(10):
        user = CreateUser(
            email=f"user{i}@gmail.com",
            full_name=f"Test User {i}",
            disabled=False,
            email_verified=True,
            auth_method=AuthProvider.EMAIL,
            photo=None,
            hashed_password="hashed_password",
        )
        fetched_user = await repo.create_user(user)
        users.append(fetched_user)

        member = await repo.create_organization_member(
            OrganizationMemberCreate(
                user_id=fetched_user.id,
                organization_id=organization.id,
                role=OrgRole.MEMBER,
            )
        )
        members.append(member)

    for i in range(5):
        invited_by_user = random.choice(users)
        invite = await invites_repo.create_organization_invite(
            CreateOrganizationInvite(
                email=f"invited_{i}_@gmail.com",
                role=OrgRole.MEMBER,
                organization_id=organization.id,
                invited_by=invited_by_user.id,
            )
        )
        invites.append(invite)

    return {
        "engine": engine,
        "repo": repo,
        "organization": organization,
        "members": members,
        "invites": invites,
        "user_owner": user_main,
    }


@pytest_asyncio.fixture(scope="function")
async def create_orbit(
    create_database_and_apply_migrations: str, test_user: dict
) -> dict:
    engine = create_async_engine(create_database_and_apply_migrations)
    user_repo = UserRepository(engine)
    secret_repo = BucketSecretRepository(engine)
    repo = OrbitRepository(engine)

    user = await user_repo.create_user(CreateUser(**test_user))
    created_organization = await user_repo.create_organization(
        user.id, OrganizationCreateIn(name="test org")
    )
    secret = await secret_repo.create_bucket_secret(
        BucketSecretCreate(
            organization_id=created_organization.id,
            endpoint="s3",
            bucket_name="test-bucket",
        )
    )
    created_orbit = await repo.create_orbit(
        created_organization.id,
        OrbitCreateIn(name="test orbit", bucket_secret_id=secret.id),
    )

    return {
        "engine": engine,
        "repo": repo,
        "organization": created_organization,
        "orbit": created_orbit,
        "bucket_secret": secret,
        "user": user,
    }


@pytest_asyncio.fixture(scope="function")
async def create_orbit_with_members(
    create_database_and_apply_migrations: str, test_user: dict
) -> dict:
    engine = create_async_engine(create_database_and_apply_migrations)
    user_repo = UserRepository(engine)
    secret_repo = BucketSecretRepository(engine)
    repo = OrbitRepository(engine)

    user = await user_repo.create_user(CreateUser(**test_user))

    created_organization = await user_repo.create_organization(
        user.id, OrganizationCreateIn(name="test org")
    )
    secret = await secret_repo.create_bucket_secret(
        BucketSecretCreate(
            organization_id=created_organization.id,
            endpoint="s3",
            bucket_name="test-bucket",
        )
    )
    created_orbit = await repo.create_orbit(
        created_organization.id,
        OrbitCreateIn(name="test orbit", bucket_secret_id=secret.id),
    )

    members = []

    for i in range(10):
        new_user = test_user.copy()
        new_user["email"] = f"email_user_{i}@example.com"
        created_user = await user_repo.create_user(CreateUser(**new_user))
        member = await repo.create_orbit_member(
            OrbitMemberCreate(
                user_id=created_user.id,
                orbit_id=created_orbit.id,
                role=random.choice([OrbitRole.MEMBER, OrbitRole.ADMIN]),
            )
        )
        if member:
            members.append(member)

    return {
        "engine": engine,
        "repo": repo,
        "organization": created_organization,
        "orbit": created_orbit,
        "bucket_secret": secret,
        "members": members,
    }
