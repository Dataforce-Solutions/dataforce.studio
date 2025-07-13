import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from dataforce_studio.repositories.users import UserRepository
from dataforce_studio.schemas.organization import (
    OrganizationCreateIn,
    OrganizationMemberCreate,
    OrgRole,
    UpdateOrganizationMember,
)
from dataforce_studio.schemas.user import AuthProvider, CreateUser


@pytest.mark.asyncio
async def test_create_organization_member(
    create_database_and_apply_migrations: str,
) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = UserRepository(engine)

    owner = await repo.create_user(
        CreateUser(
            email="owner@example.com",
            full_name="Owner User",
            disabled=False,
            email_verified=True,
            auth_method=AuthProvider.EMAIL,
            photo=None,
            hashed_password="hashed_password",
        )
    )
    organization = await repo.create_organization(
        owner.id, OrganizationCreateIn(name="Test Organization")
    )

    user = await repo.create_user(
        CreateUser(
            email="member@example.com",
            full_name="Member User",
            disabled=False,
            email_verified=True,
            auth_method=AuthProvider.EMAIL,
            photo=None,
            hashed_password="hashed_password",
        )
    )

    created_member = await repo.create_organization_member(
        OrganizationMemberCreate(
            user_id=user.id,
            organization_id=organization.id,
            role=OrgRole.MEMBER,
        )
    )

    assert created_member.id
    assert created_member.organization_id == organization.id
    assert created_member.user.id == user.id
    assert created_member.role == OrgRole.MEMBER


@pytest.mark.asyncio
async def test_update_organization_member(
    create_database_and_apply_migrations: str,
) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = UserRepository(engine)

    user = await repo.create_user(
        CreateUser(
            email="testuser@example.com",
            full_name="Test User",
            disabled=False,
            email_verified=True,
            auth_method=AuthProvider.EMAIL,
            photo=None,
            hashed_password="hashed_password",
        )
    )
    organization = await repo.create_organization(
        user.id, OrganizationCreateIn(name="Test Organization")
    )
    member = await repo.get_organization_member(organization.id, user.id)

    updated_member = await repo.update_organization_member(
        member.id, UpdateOrganizationMember(role=OrgRole.ADMIN)
    )

    assert updated_member.id == member.id
    assert updated_member.role == OrgRole.ADMIN


@pytest.mark.asyncio
async def test_delete_organization_member(
    create_database_and_apply_migrations: str,
) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = UserRepository(engine)

    user = await repo.create_user(
        CreateUser(
            email="testuser@example.com",
            full_name="Test User",
            disabled=False,
            email_verified=True,
            auth_method=AuthProvider.EMAIL,
            photo=None,
            hashed_password="hashed_password",
        )
    )
    organization = await repo.create_organization(
        user.id, OrganizationCreateIn(name="Test Organization")
    )

    member = await repo.get_organization_member(organization.id, user.id)

    deleted_member = await repo.delete_organization_member(member.id)
    org_members_count = await repo.get_organization_members_count(organization.id)

    assert deleted_member is None
    assert org_members_count == 0 or org_members_count is None


@pytest.mark.asyncio
async def test_get_organization_members_count(
    create_database_and_apply_migrations: str,
) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = UserRepository(engine)

    main_user = await repo.create_user(
        CreateUser(
            email="main@example.com",
            full_name="Main User",
            disabled=False,
            email_verified=True,
            auth_method=AuthProvider.EMAIL,
            photo=None,
            hashed_password="hashed_password",
        )
    )
    organization = await repo.create_organization(
        main_user.id, OrganizationCreateIn(name="Test Organization")
    )

    members = []
    for i in range(3):
        user = await repo.create_user(
            CreateUser(
                email=f"user{i}@example.com",
                full_name=f"User {i}",
                disabled=False,
                email_verified=True,
                auth_method=AuthProvider.EMAIL,
                photo=None,
                hashed_password="hashed_password",
            )
        )
        member = await repo.create_organization_member(
            OrganizationMemberCreate(
                user_id=user.id,
                organization_id=organization.id,
                role=OrgRole.MEMBER,
            )
        )
        members.append(member)

    count = await repo.get_organization_members_count(organization.id)

    assert len(members) + 1 == count


@pytest.mark.asyncio
async def test_get_organization_members(
    create_database_and_apply_migrations: str,
) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = UserRepository(engine)

    main_user = await repo.create_user(
        CreateUser(
            email="main@example.com",
            full_name="Main User",
            disabled=False,
            email_verified=True,
            auth_method=AuthProvider.EMAIL,
            photo=None,
            hashed_password="hashed_password",
        )
    )
    organization = await repo.create_organization(
        main_user.id, OrganizationCreateIn(name="Test Organization")
    )

    additional_users = []
    for i in range(3):
        user = await repo.create_user(
            CreateUser(
                email=f"user{i}@example.com",
                full_name=f"User {i}",
                disabled=False,
                email_verified=True,
                auth_method=AuthProvider.EMAIL,
                photo=None,
                hashed_password="hashed_password",
            )
        )
        await repo.create_organization_member(
            OrganizationMemberCreate(
                user_id=user.id,
                organization_id=organization.id,
                role=OrgRole.MEMBER,
            )
        )
        additional_users.append(user)

    db_members = await repo.get_organization_members(organization.id)

    assert db_members
    assert len(db_members) == 4
    assert db_members[0].id
    assert db_members[0].organization_id == organization.id
    assert db_members[0].user.id
