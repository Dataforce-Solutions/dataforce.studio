import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from dataforce_studio.repositories.bucket_secrets import BucketSecretRepository
from dataforce_studio.repositories.orbits import OrbitRepository
from dataforce_studio.repositories.users import UserRepository
from dataforce_studio.schemas.bucket_secrets import BucketSecretCreate
from dataforce_studio.schemas.orbit import (
    Orbit,
    OrbitCreateIn,
    OrbitDetails,
    OrbitMember,
    OrbitMemberCreate,
    OrbitRole,
    OrbitUpdate,
    UpdateOrbitMember,
)
from dataforce_studio.schemas.organization import OrganizationCreateIn
from dataforce_studio.schemas.user import AuthProvider, CreateUser


@pytest.mark.asyncio
async def test_create_orbit(create_database_and_apply_migrations: str) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    user_repo = UserRepository(engine)
    secret_repo = BucketSecretRepository(engine)
    orbit_repo = OrbitRepository(engine)

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
        user.id, OrganizationCreateIn(name="Test Organization")
    )

    secret = await secret_repo.create_bucket_secret(
        BucketSecretCreate(
            organization_id=organization.id,
            endpoint="s3",
            bucket_name="test-bucket",
        )
    )

    orbit = OrbitCreateIn(name="test orbit", bucket_secret_id=secret.id)
    created_orbit = await orbit_repo.create_orbit(organization.id, orbit)

    assert created_orbit.id
    assert created_orbit.name == orbit.name
    assert created_orbit.organization_id == organization.id


@pytest.mark.asyncio
async def test_update_orbit(create_database_and_apply_migrations: str) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    user_repo = UserRepository(engine)
    secret_repo = BucketSecretRepository(engine)
    orbit_repo = OrbitRepository(engine)

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
        user.id, OrganizationCreateIn(name="Test Organization")
    )
    secret = await secret_repo.create_bucket_secret(
        BucketSecretCreate(
            organization_id=organization.id,
            endpoint="s3",
            bucket_name="test-bucket",
        )
    )

    orbit = OrbitCreateIn(name="test orbit", bucket_secret_id=secret.id)
    created_orbit = await orbit_repo.create_orbit(organization.id, orbit)

    updated_orbit = await orbit_repo.update_orbit(
        created_orbit.id, OrbitUpdate(name=created_orbit.name + "updated")
    )

    assert updated_orbit
    assert updated_orbit.id == created_orbit.id
    assert updated_orbit.name == created_orbit.name + "updated"


@pytest.mark.asyncio
async def test_attach_bucket_secret(create_database_and_apply_migrations: str) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    user_repo = UserRepository(engine)
    secret_repo = BucketSecretRepository(engine)
    orbit_repo = OrbitRepository(engine)

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
        user.id, OrganizationCreateIn(name="Test Organization")
    )
    secret = await secret_repo.create_bucket_secret(
        BucketSecretCreate(
            organization_id=organization.id,
            endpoint="s3",
            bucket_name="initial-bucket",
        )
    )

    orbit = await orbit_repo.create_orbit(
        organization.id, OrbitCreateIn(name="test", bucket_secret_id=secret.id)
    )

    new_secret = await secret_repo.create_bucket_secret(
        BucketSecretCreate(
            organization_id=organization.id, endpoint="s3", bucket_name="new-bucket"
        )
    )

    updated = await orbit_repo.update_orbit(
        orbit.id, OrbitUpdate(name=orbit.name, bucket_secret_id=new_secret.id)
    )

    assert updated.bucket_secret_id == new_secret.id


@pytest.mark.asyncio
async def test_delete_orbit(create_database_and_apply_migrations: str) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    user_repo = UserRepository(engine)
    secret_repo = BucketSecretRepository(engine)
    orbit_repo = OrbitRepository(engine)

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
        user.id, OrganizationCreateIn(name="Test Organization")
    )
    secret = await secret_repo.create_bucket_secret(
        BucketSecretCreate(
            organization_id=organization.id,
            endpoint="s3",
            bucket_name="test-bucket",
        )
    )

    orbit = await orbit_repo.create_orbit(
        organization.id, OrbitCreateIn(name="test orbit", bucket_secret_id=secret.id)
    )

    deleted_orbit = await orbit_repo.delete_orbit(orbit.id)
    fetched_orbit = await orbit_repo.get_orbit_simple(orbit.id, orbit.organization_id)

    assert deleted_orbit is None
    assert fetched_orbit is None


@pytest.mark.asyncio
async def test_get_orbit(create_database_and_apply_migrations: str) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    user_repo = UserRepository(engine)
    secret_repo = BucketSecretRepository(engine)
    orbit_repo = OrbitRepository(engine)

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
        user.id, OrganizationCreateIn(name="Test Organization")
    )
    secret = await secret_repo.create_bucket_secret(
        BucketSecretCreate(
            organization_id=organization.id,
            endpoint="s3",
            bucket_name="test-bucket",
        )
    )

    orbit = await orbit_repo.create_orbit(
        organization.id, OrbitCreateIn(name="test orbit", bucket_secret_id=secret.id)
    )

    fetched_orbit = await orbit_repo.get_orbit(orbit.id, orbit.organization_id)

    assert fetched_orbit
    assert isinstance(fetched_orbit, OrbitDetails)
    assert fetched_orbit.id == orbit.id
    assert fetched_orbit.name == orbit.name
    assert fetched_orbit.organization_id == orbit.organization_id


@pytest.mark.asyncio
async def test_get_organization_orbits(
    create_database_and_apply_migrations: str,
) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    user_repo = UserRepository(engine)
    secret_repo = BucketSecretRepository(engine)
    orbit_repo = OrbitRepository(engine)

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
        user.id, OrganizationCreateIn(name="Test Organization")
    )
    secret = await secret_repo.create_bucket_secret(
        BucketSecretCreate(
            organization_id=organization.id,
            endpoint="s3",
            bucket_name="test-bucket",
        )
    )

    for i in range(5):
        await orbit_repo.create_orbit(
            organization.id,
            OrbitCreateIn(name=f"orbit #{i}", bucket_secret_id=secret.id),
        )

    orbits = await orbit_repo.get_organization_orbits(organization.id)

    assert orbits
    assert isinstance(orbits, list)
    assert len(orbits) == 5
    assert isinstance(orbits[0], Orbit)


@pytest.mark.asyncio
async def test_get_orbit_members(create_database_and_apply_migrations: str) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    user_repo = UserRepository(engine)
    secret_repo = BucketSecretRepository(engine)
    orbit_repo = OrbitRepository(engine)

    owner = await user_repo.create_user(
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
    organization = await user_repo.create_organization(
        owner.id, OrganizationCreateIn(name="Test Organization")
    )
    secret = await secret_repo.create_bucket_secret(
        BucketSecretCreate(
            organization_id=organization.id,
            endpoint="s3",
            bucket_name="test-bucket",
        )
    )
    orbit = await orbit_repo.create_orbit(
        organization.id, OrbitCreateIn(name="test orbit", bucket_secret_id=secret.id)
    )

    members = []
    for i in range(3):
        user = await user_repo.create_user(
            CreateUser(
                email=f"member{i}@example.com",
                full_name=f"Member User {i}",
                disabled=False,
                email_verified=True,
                auth_method=AuthProvider.EMAIL,
                photo=None,
                hashed_password="hashed_password",
            )
        )
        member = await orbit_repo.create_orbit_member(
            OrbitMemberCreate(user_id=user.id, orbit_id=orbit.id, role=OrbitRole.MEMBER)
        )
        members.append(member)

    orbit_members = await orbit_repo.get_orbit_members(orbit.id)

    assert orbit_members
    assert isinstance(orbit_members, list)
    assert len(orbit_members) == len(members)
    assert isinstance(orbit_members[0], OrbitMember)
    assert orbit_members[0].orbit_id == orbit.id


@pytest.mark.asyncio
async def test_create_orbit_member(create_database_and_apply_migrations: str) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    user_repo = UserRepository(engine)
    secret_repo = BucketSecretRepository(engine)
    orbit_repo = OrbitRepository(engine)

    owner = await user_repo.create_user(
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
    organization = await user_repo.create_organization(
        owner.id, OrganizationCreateIn(name="Test Organization")
    )
    secret = await secret_repo.create_bucket_secret(
        BucketSecretCreate(
            organization_id=organization.id,
            endpoint="s3",
            bucket_name="test-bucket",
        )
    )
    orbit = await orbit_repo.create_orbit(
        organization.id, OrbitCreateIn(name="test orbit", bucket_secret_id=secret.id)
    )
    user = await user_repo.create_user(
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
    created_member = await orbit_repo.create_orbit_member(
        OrbitMemberCreate(user_id=user.id, orbit_id=orbit.id, role=OrbitRole.MEMBER)
    )

    assert created_member
    assert isinstance(created_member, OrbitMember)


@pytest.mark.asyncio
async def test_update_orbit_member(create_database_and_apply_migrations: str) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    user_repo = UserRepository(engine)
    secret_repo = BucketSecretRepository(engine)
    orbit_repo = OrbitRepository(engine)

    owner = await user_repo.create_user(
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
    organization = await user_repo.create_organization(
        owner.id, OrganizationCreateIn(name="Test Organization")
    )
    secret = await secret_repo.create_bucket_secret(
        BucketSecretCreate(
            organization_id=organization.id,
            endpoint="s3",
            bucket_name="test-bucket",
        )
    )
    orbit = await orbit_repo.create_orbit(
        organization.id, OrbitCreateIn(name="test orbit", bucket_secret_id=secret.id)
    )

    user = await user_repo.create_user(
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

    created_member = await orbit_repo.create_orbit_member(
        OrbitMemberCreate(user_id=user.id, orbit_id=orbit.id, role=OrbitRole.MEMBER)
    )
    updated_member = await orbit_repo.update_orbit_member(
        UpdateOrbitMember(id=created_member.id, role=OrbitRole.ADMIN)
    )

    assert updated_member
    assert isinstance(updated_member, OrbitMember)
    assert updated_member.role == OrbitRole.ADMIN


@pytest.mark.asyncio
async def test_delete_orbit_member(create_database_and_apply_migrations: str) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    user_repo = UserRepository(engine)
    secret_repo = BucketSecretRepository(engine)
    orbit_repo = OrbitRepository(engine)

    owner = await user_repo.create_user(
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
    organization = await user_repo.create_organization(
        owner.id, OrganizationCreateIn(name="Test Organization")
    )
    secret = await secret_repo.create_bucket_secret(
        BucketSecretCreate(
            organization_id=organization.id,
            endpoint="s3",
            bucket_name="test-bucket",
        )
    )
    orbit = await orbit_repo.create_orbit(
        organization.id, OrbitCreateIn(name="test orbit", bucket_secret_id=secret.id)
    )
    user = await user_repo.create_user(
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
    created_member = await orbit_repo.create_orbit_member(
        OrbitMemberCreate(user_id=user.id, orbit_id=orbit.id, role=OrbitRole.MEMBER)
    )
    deleted_member = await orbit_repo.delete_orbit_member(created_member.id)

    assert deleted_member is None
