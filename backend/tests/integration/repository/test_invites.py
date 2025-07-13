import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from dataforce_studio.repositories.bucket_secrets import BucketSecretRepository
from dataforce_studio.repositories.invites import InviteRepository
from dataforce_studio.repositories.users import UserRepository
from dataforce_studio.schemas.bucket_secrets import BucketSecretCreate
from dataforce_studio.schemas.organization import (
    CreateOrganizationInvite,
    OrganizationCreateIn,
    OrgRole,
)
from dataforce_studio.schemas.user import AuthProvider, CreateUser


@pytest.mark.asyncio
async def test_create_organization_invite(
    create_database_and_apply_migrations: str,
) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    user_repo = UserRepository(engine)
    secret_repo = BucketSecretRepository(engine)
    invite_repo = InviteRepository(engine)

    create_user_data = CreateUser(
        email="testuser@example.com",
        full_name="Test User",
        disabled=False,
        email_verified=True,
        auth_method=AuthProvider.EMAIL,
        photo=None,
        hashed_password="hashed_password",
    )
    user = await user_repo.create_user(create_user_data)
    organization = await user_repo.create_organization(
        user.id, OrganizationCreateIn(name="test org")
    )
    await secret_repo.create_bucket_secret(
        BucketSecretCreate(
            organization_id=organization.id,
            endpoint="s3",
            bucket_name="test-bucket",
        )
    )

    invite = CreateOrganizationInvite(
        email="test@gmail.com",
        role=OrgRole.MEMBER,
        organization_id=organization.id,
        invited_by=user.id,
    )

    created_invite = await invite_repo.create_organization_invite(invite)

    assert created_invite.email == invite.email
    assert created_invite.organization_id == invite.organization_id


@pytest.mark.asyncio
async def test_delete_organization_invite(
    create_database_and_apply_migrations: str,
) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    user_repo = UserRepository(engine)
    secret_repo = BucketSecretRepository(engine)
    invite_repo = InviteRepository(engine)

    create_user_data = CreateUser(
        email="testuser@example.com",
        full_name="Test User",
        disabled=False,
        email_verified=True,
        auth_method=AuthProvider.EMAIL,
        photo=None,
        hashed_password="hashed_password",
    )
    user = await user_repo.create_user(create_user_data)
    organization = await user_repo.create_organization(
        user.id, OrganizationCreateIn(name="test org")
    )

    await secret_repo.create_bucket_secret(
        BucketSecretCreate(
            organization_id=organization.id,
            endpoint="s3",
            bucket_name="test-bucket",
        )
    )

    invite = CreateOrganizationInvite(
        email="test@gmail.com",
        role=OrgRole.MEMBER,
        organization_id=organization.id,
        invited_by=user.id,
    )
    created_invite = await invite_repo.create_organization_invite(invite)
    deleted_invite = await invite_repo.delete_organization_invite(created_invite.id)

    assert deleted_invite is None


@pytest.mark.asyncio
async def test_get_invite(create_database_and_apply_migrations: str) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    user_repo = UserRepository(engine)
    secret_repo = BucketSecretRepository(engine)
    invite_repo = InviteRepository(engine)

    create_user_data = CreateUser(
        email="testuser@example.com",
        full_name="Test User",
        disabled=False,
        email_verified=True,
        auth_method=AuthProvider.EMAIL,
        photo=None,
        hashed_password="hashed_password",
    )
    user = await user_repo.create_user(create_user_data)
    organization = await user_repo.create_organization(
        user.id, OrganizationCreateIn(name="test org")
    )

    await secret_repo.create_bucket_secret(
        BucketSecretCreate(
            organization_id=organization.id,
            endpoint="s3",
            bucket_name="test-bucket",
        )
    )

    created_invite = await invite_repo.create_organization_invite(
        CreateOrganizationInvite(
            email="test@gmail.com",
            role=OrgRole.MEMBER,
            organization_id=organization.id,
            invited_by=user.id,
        )
    )

    fetched_invite = await invite_repo.get_invite(created_invite.id)

    assert fetched_invite.id == created_invite.id
    assert fetched_invite.email == created_invite.email
    assert fetched_invite.invited_by_user.id == user.id
    assert fetched_invite.organization_id == created_invite.organization_id


@pytest.mark.asyncio
async def test_get_invite_where(create_database_and_apply_migrations: str) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    user_repo = UserRepository(engine)
    secret_repo = BucketSecretRepository(engine)
    repo = InviteRepository(engine)

    user = await user_repo.create_user(
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
    organization = await user_repo.create_organization(
        user.id, OrganizationCreateIn(name="test org")
    )

    await secret_repo.create_bucket_secret(
        BucketSecretCreate(
            organization_id=organization.id,
            endpoint="s3",
            bucket_name="test-bucket",
        )
    )

    for i in range(4):
        await repo.create_organization_invite(
            CreateOrganizationInvite(
                email=f"{i}_test@gmail.com",
                role=OrgRole.MEMBER,
                organization_id=organization.id,
                invited_by=user.id,
            )
        )

    invites = await repo.get_invites_by_organization_id(organization.id)

    assert isinstance(invites, list)
    assert len(invites) == 4
    assert invites[0].organization_id == organization.id


@pytest.mark.asyncio
async def test_delete_invite_where(create_database_and_apply_migrations: str) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    user_repo = UserRepository(engine)
    secret_repo = BucketSecretRepository(engine)
    invite_repo = InviteRepository(engine)

    create_user_data = CreateUser(
        email="testuser@example.com",
        full_name="Test User",
        disabled=False,
        email_verified=True,
        auth_method=AuthProvider.EMAIL,
        photo=None,
        hashed_password="hashed_password",
    )
    user = await user_repo.create_user(create_user_data)
    organization = await user_repo.create_organization(
        user.id, OrganizationCreateIn(name="test org")
    )

    await secret_repo.create_bucket_secret(
        BucketSecretCreate(
            organization_id=organization.id,
            endpoint="s3",
            bucket_name="test-bucket",
        )
    )

    for i in range(4):
        await invite_repo.create_organization_invite(
            CreateOrganizationInvite(
                email=f"{i}_test@gmail.com",
                role=OrgRole.MEMBER,
                organization_id=organization.id,
                invited_by=user.id,
            )
        )

    deleted_invites = await invite_repo.delete_all_organization_invites(organization.id)
    invites = await invite_repo.get_invites_by_organization_id(organization.id)

    assert deleted_invites is None
    assert len(invites) == 0
