import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from dataforce_studio.repositories.bucket_secrets import BucketSecretRepository
from dataforce_studio.repositories.collections import CollectionRepository
from dataforce_studio.repositories.orbits import OrbitRepository
from dataforce_studio.repositories.users import UserRepository
from dataforce_studio.schemas.bucket_secrets import BucketSecretCreate
from dataforce_studio.schemas.ml_models import CollectionCreate, CollectionType
from dataforce_studio.schemas.orbit import OrbitCreateIn
from dataforce_studio.schemas.organization import OrganizationCreateIn
from dataforce_studio.schemas.user import AuthProvider, CreateUser


@pytest.mark.asyncio
async def test_create_collection(create_database_and_apply_migrations: str) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    user_repo = UserRepository(engine)
    secret_repo = BucketSecretRepository(engine)
    orbit_repo = OrbitRepository(engine)
    collection_repo = CollectionRepository(engine)

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

    collection = CollectionCreate(
        orbit_id=orbit.id,
        description="desc",
        name="model-1",
        collection_type=CollectionType.MODEL,
    )
    created = await collection_repo.create_collection(collection)

    assert created.id
    assert created.orbit_id == orbit.id
    assert created.name == collection.name
