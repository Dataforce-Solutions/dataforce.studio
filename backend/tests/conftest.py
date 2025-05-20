import datetime
import random
from uuid import uuid4

import asyncpg
import pytest_asyncio
from dataforce_studio.models import OrganizationInviteOrm
from dataforce_studio.repositories.invites import InviteRepository
from dataforce_studio.repositories.orbits import OrbitRepository
from dataforce_studio.repositories.users import UserRepository
from dataforce_studio.schemas.orbit import OrbitCreate, OrbitMemberCreate, OrbitRole
from dataforce_studio.schemas.organization import (
    OrganizationInvite,
    OrganizationMember,
    OrgRole,
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


invite_data = {
    "email": "test@example.com",
    "role": OrgRole.MEMBER,
    "organization_id": uuid4(),
    "invited_by": uuid4(),
}

invite_get_data = {
    "id": uuid4(),
    "email": "test@example.com",
    "role": OrgRole.MEMBER,
    "organization_id": uuid4(),
    "invited_by": uuid4(),
    "created_at": datetime.datetime.now(),
}

invite_accept_data = {
    "id": uuid4(),
    "email": "test@example.com",
    "role": OrgRole.MEMBER,
    "organization_id": uuid4(),
    "invited_by": uuid4(),
}
member_data = {
    "id": uuid4(),
    "organization_id": uuid4(),
    "role": OrgRole.ADMIN,
    "user": {
        "id": uuid4(),
        "email": "test@gmail.com",
        "full_name": "Full Name",
        "disabled": False,
        "photo": None,
    },
}


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
def test_org() -> dict:
    return {
        "id": uuid4(),
        "name": "Test organization",
        "logo": None,
        "created_at": datetime.datetime.now(),
        "updated_at": datetime.datetime.now(),
    }


@pytest_asyncio.fixture(scope="function")
def test_org_details() -> dict:
    return {
        "id": uuid4(),
        "name": "Test organization",
        "logo": None,
        "created_at": datetime.datetime.now(),
        "updated_at": datetime.datetime.now(),
        "invites": [OrganizationInvite(**invite_get_data)],
        "members": [OrganizationMember(**member_data)],
    }


@pytest_asyncio.fixture(scope="function")
async def create_organization_with_user(
    create_database_and_apply_migrations: str, test_user: dict
) -> dict:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = UserRepository(engine)

    created_organization = await repo.create_organization("test org", None)
    await repo.create_user(CreateUser(**test_user))
    fetched_user = await repo.get_user(test_user["email"])

    return {
        "engine": engine,
        "repo": repo,
        "user": fetched_user,
        "organization": created_organization,
    }


@pytest_asyncio.fixture(scope="function")
async def create_organization_with_members(
    create_database_and_apply_migrations: str,
) -> dict:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = UserRepository(engine)
    invites_repo = InviteRepository(engine)

    organization = await repo.create_organization(
        name="Test org with members", logo=None
    )

    members = []
    users = []
    invites = []

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
            user_id=fetched_user.id,
            organization_id=organization.id,
            role=OrgRole.MEMBER,
        )
        members.append(member)

    for i in range(5):
        invited_by_user = random.choice(users)
        invite = await invites_repo.create_organization_invite(
            OrganizationInviteOrm(
                email=f"invited_{i}_@gmail.com",
                organization_id=organization.id,
                invited_by=invited_by_user.id,
                role=OrgRole.MEMBER,
            )
        )
        invites.append(invite)

    return {
        "engine": engine,
        "repo": repo,
        "organization": organization,
        "members": members,
        "invites": invites,
    }


@pytest_asyncio.fixture(scope="function")
async def create_orbit(
    create_database_and_apply_migrations: str, test_user: dict
) -> dict:
    engine = create_async_engine(create_database_and_apply_migrations)
    user_repo = UserRepository(engine)
    repo = OrbitRepository(engine)

    user = await user_repo.create_user(CreateUser(**test_user))
    created_organization = await user_repo.create_organization("test org", None)
    created_orbit = await repo.create_orbit(
        OrbitCreate(name="test orbit", organization_id=created_organization.id)
    )

    return {
        "engine": engine,
        "repo": repo,
        "organization": created_organization,
        "orbit": created_orbit,
        "user": user,
    }


@pytest_asyncio.fixture(scope="function")
async def create_orbit_with_members(
    create_database_and_apply_migrations: str, test_user: dict
) -> dict:
    engine = create_async_engine(create_database_and_apply_migrations)
    user_repo = UserRepository(engine)
    repo = OrbitRepository(engine)
    created_organization = await user_repo.create_organization("test org", None)
    created_orbit = await repo.create_orbit(
        OrbitCreate(name="test orbit", organization_id=created_organization.id)
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
        "members": members,
    }
