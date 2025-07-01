import pytest
from dataforce_studio.repositories.bucket_secrets import BucketSecretRepository
from dataforce_studio.repositories.orbits import OrbitRepository
from dataforce_studio.schemas.bucket_secrets import BucketSecretCreate
from dataforce_studio.schemas.orbit import (
    Orbit,
    OrbitCreate,
    OrbitDetails,
    OrbitMember,
    OrbitMemberCreate,
    OrbitRole,
    OrbitUpdate,
    UpdateOrbitMember,
    OrbitCreateIn,
)


@pytest.mark.asyncio
async def test_create_orbit(create_organization_with_user: dict) -> None:
    data = create_organization_with_user
    engine, organization, secret = (
        data["engine"],
        data["organization"],
        data["bucket_secret"],
    )
    repo = OrbitRepository(engine)

    orbit = OrbitCreateIn(name="test orbit", bucket_secret_id=secret.id)
    created_orbit = await repo.create_orbit(organization.id, orbit)

    assert created_orbit.id
    assert created_orbit.name == orbit.name
    # assert created_orbit.organization_id == orbit.organization_id


@pytest.mark.asyncio
async def test_update_orbit(create_organization_with_user: dict) -> None:
    data = create_organization_with_user
    engine, organization, secret = (
        data["engine"],
        data["organization"],
        data["bucket_secret"],
    )
    repo = OrbitRepository(engine)

    orbit = OrbitCreateIn(name="test orbit", bucket_secret_id=secret.id)
    created_orbit = await repo.create_orbit(organization.id, orbit)

    new_name = created_orbit.name + "updated"
    updated_orbit = await repo.update_orbit(
        created_orbit.id, OrbitUpdate(name=new_name)
    )

    assert updated_orbit
    assert updated_orbit.id == created_orbit.id
    assert updated_orbit.name == new_name


@pytest.mark.asyncio
async def test_attach_bucket_secret(create_organization_with_user: dict) -> None:
    data = create_organization_with_user
    engine, organization, secret = (
        data["engine"],
        data["organization"],
        data["bucket_secret"],
    )
    repo = OrbitRepository(engine)
    secret_repo = BucketSecretRepository(engine)

    orbit = await repo.create_orbit(
        organization.id, OrbitCreateIn(name="test", bucket_secret_id=secret.id)
    )
    secret = await secret_repo.create_bucket_secret(
        BucketSecretCreate(
            organization_id=organization.id, endpoint="s3", bucket_name="test-bucket"
        )
    )

    updated = await repo.update_orbit(
        orbit.id, OrbitUpdate(name=orbit.name, bucket_secret_id=secret.id)
    )

    assert updated.bucket_secret_id == secret.id


@pytest.mark.asyncio
async def test_delete_orbit(create_orbit: dict) -> None:
    data = create_orbit
    repo, orbit = data["repo"], data["orbit"]

    deleted_orbit = await repo.delete_orbit(orbit.id)
    fetched_orbit = await repo.get_orbit_simple(orbit.id, orbit.organization_id)

    assert deleted_orbit is None
    assert fetched_orbit is None


@pytest.mark.asyncio
async def test_get_orbit(create_orbit: dict) -> None:
    data = create_orbit
    repo, orbit = data["repo"], data["orbit"]

    fetched_orbit = await repo.get_orbit(orbit.id, orbit.organization_id)

    assert fetched_orbit
    assert isinstance(fetched_orbit, OrbitDetails)
    assert fetched_orbit.id == orbit.id
    assert fetched_orbit.name == orbit.name
    assert fetched_orbit.organization_id == orbit.organization_id


@pytest.mark.asyncio
async def test_get_organization_orbits(create_organization_with_user: dict) -> None:
    data = create_organization_with_user
    engine, organization, secret = (
        data["engine"],
        data["organization"],
        data["bucket_secret"],
    )
    repo = OrbitRepository(engine)

    for i in range(5):
        await repo.create_orbit(
            organization.id,
            OrbitCreateIn(name=f"orbit #{i}", bucket_secret_id=secret.id),
        )

    orbits = await repo.get_organization_orbits(organization.id)

    assert orbits
    assert isinstance(orbits, list)
    assert len(orbits) == 5
    assert isinstance(orbits[0], Orbit)


@pytest.mark.asyncio
async def test_get_orbit_members(create_orbit_with_members: dict) -> None:
    data = create_orbit_with_members
    repo, orbit, members = data["repo"], data["orbit"], data["members"]

    orbit_members = await repo.get_orbit_members(orbit.id)

    assert orbit_members
    assert isinstance(orbit_members, list)
    assert len(orbit_members) == len(members)
    assert isinstance(orbit_members[0], OrbitMember)
    assert orbit_members[0].orbit_id == orbit.id


@pytest.mark.asyncio
async def test_create_orbit_member(create_orbit: dict) -> None:
    data = create_orbit
    repo, orbit, user = (
        data["repo"],
        data["orbit"],
        data["user"],
    )

    member = OrbitMemberCreate(
        user_id=user.id, orbit_id=orbit.id, role=OrbitRole.MEMBER
    )
    created_member = await repo.create_orbit_member(member)

    assert created_member
    assert isinstance(created_member, OrbitMember)


@pytest.mark.asyncio
async def test_update_orbit_member(create_orbit: dict) -> None:
    data = create_orbit
    repo, orbit, user = (
        data["repo"],
        data["orbit"],
        data["user"],
    )

    member = OrbitMemberCreate(
        user_id=user.id, orbit_id=orbit.id, role=OrbitRole.MEMBER
    )
    created_member = await repo.create_orbit_member(member)

    updated_member = await repo.update_orbit_member(
        UpdateOrbitMember(id=created_member.id, role=OrbitRole.ADMIN)
    )

    assert updated_member
    assert isinstance(updated_member, OrbitMember)
    assert updated_member.role == OrbitRole.ADMIN


@pytest.mark.asyncio
async def test_delete_orbit_member(create_orbit: dict) -> None:
    data = create_orbit
    repo, orbit, user = (
        data["repo"],
        data["orbit"],
        data["user"],
    )

    member = OrbitMemberCreate(
        user_id=user.id, orbit_id=orbit.id, role=OrbitRole.MEMBER
    )
    created_member = await repo.create_orbit_member(member)

    deleted_member = await repo.delete_orbit_member(created_member.id)

    assert deleted_member is None
