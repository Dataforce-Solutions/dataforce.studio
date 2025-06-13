import random
from unittest.mock import AsyncMock, patch

import pytest
from dataforce_studio.handlers.orbits import OrbitHandler
from dataforce_studio.infra.exceptions import NotFoundError
from dataforce_studio.schemas.orbit import (
    Orbit,
    OrbitCreate,
    OrbitDetails,
    OrbitMember,
    OrbitMemberCreate,
    OrbitRole,
    OrbitUpdate,
    UpdateOrbitMember,
)
from dataforce_studio.schemas.organization import OrgRole

handler = OrbitHandler()

test_orbit = {
    "name": "test",
    "organization_id": random.randint(1, 10000),
    "total_members": 1,
    "created_at": "2025-05-17T09:52:38.234961Z",
    "updated_at": "2025-05-17T09:52:38.234961Z",
}

test_orbit_created = {
    "id": random.randint(1, 10000),
    "name": "test",
    "organization_id": random.randint(1, 10000),
    "total_members": 0,
    "created_at": "2025-05-17T09:52:38.234961Z",
    "updated_at": None
}

test_orbit_id = random.randint(1, 10000)

test_orbit_member = {
    "id": 8766,
    "orbit_id": test_orbit_id,
    "role": OrbitRole.MEMBER,
    "user": {
        "id": random.randint(1, 10000),
        "email": "brandihernandez@example.org",
        "full_name": "Kathy Hall",
        "disabled": False,
        "photo": None,
    },
    "created_at": "2025-05-17T09:52:38.234961Z",
    "updated_at": "2025-05-17T09:52:38.234961Z",
}

test_orbit_details = {
    "id": test_orbit_id,
    "name": "test",
    "organization_id": random.randint(1, 10000),
    "members": [
        test_orbit_member,
    ],
    "created_at": "2025-05-17T09:52:38.234961Z",
    "updated_at": "2025-05-17T09:52:38.234961Z",
}


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.get_organization_orbits_count",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.create_orbit",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_organization_orbit(
    mock_create_orbit: AsyncMock,
    mock_get_organization_orbits_count: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    orbit_id = random.randint(1, 10000)
    user_id = random.randint(1, 10000)
    orbit_to_create = OrbitCreate(**test_orbit)
    mocked_orbit = Orbit(**test_orbit, id=orbit_id)

    mock_create_orbit.return_value = mocked_orbit
    mock_get_organization_orbits_count.return_value = 0
    mock_get_organization_member_role.return_value = OrgRole.OWNER

    result = await handler.create_organization_orbit(
        user_id, orbit_to_create.organization_id, orbit_to_create
    )

    assert result == mocked_orbit

    mock_create_orbit.assert_awaited_once_with(
        orbit_to_create.organization_id, orbit_to_create
    )


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.get_organization_orbits",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_organization_orbits(
    mock_get_organization_orbits: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    user_id = random.randint(1, 10000)
    orbit = Orbit(**test_orbit_created)
    expected = list(orbit)

    mock_get_organization_orbits.return_value = expected
    mock_get_organization_member_role.return_value = OrgRole.OWNER

    result = await handler.get_organization_orbits(user_id, orbit.organization_id)

    assert result == expected

    mock_get_organization_orbits.assert_awaited_once_with(orbit.organization_id)


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.get_orbit",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_orbit(
    mock_get_orbit: AsyncMock,
    mock_get_orbit_member_role: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    user_id = random.randint(1, 10000)
    expected = OrbitDetails(**test_orbit_details)

    mock_get_orbit.return_value = expected
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_orbit_member_role.return_value = OrgRole.ADMIN

    result = await handler.get_orbit(user_id, expected.organization_id, expected.id)

    assert result == expected
    mock_get_orbit.assert_awaited_once_with(expected.id)


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.get_orbit",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_orbit_not_found(
    mock_get_orbit: AsyncMock,
    mock_get_orbit_member_role: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)

    mock_get_orbit.return_value = None
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_orbit_member_role.return_value = OrgRole.ADMIN

    with pytest.raises(NotFoundError, match="Orbit not found") as error:
        await handler.get_orbit(user_id, organization_id, orbit_id)

    assert error.value.status_code == 404
    mock_get_orbit.assert_awaited_once_with(orbit_id)


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.update_orbit",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_orbit(
    mock_update_orbit: AsyncMock,
    mock_get_orbit_member_role: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    user_id = random.randint(1, 10000)
    expected = OrbitDetails(**test_orbit_details)

    mock_update_orbit.return_value = expected
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_orbit_member_role.return_value = OrgRole.ADMIN

    update_orbit = OrbitUpdate(name="new_name")
    result = await handler.update_orbit(
        user_id, expected.organization_id, expected.id, update_orbit
    )

    assert result == expected
    mock_update_orbit.assert_awaited_once_with(expected.id, update_orbit)


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.update_orbit",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_orbit_not_found(
    mock_update_orbit: AsyncMock,
    mock_get_orbit_member_role: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)
    update_orbit = OrbitUpdate(name="new_name")

    mock_update_orbit.return_value = None
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_orbit_member_role.return_value = OrgRole.ADMIN

    with pytest.raises(NotFoundError, match="Orbit not found") as error:
        await handler.update_orbit(user_id, organization_id, orbit_id, update_orbit)

    assert error.value.status_code == 404
    mock_update_orbit.assert_awaited_once_with(orbit_id, update_orbit)


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.delete_orbit",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_orbit(
    mock_delete_orbit: AsyncMock,
    mock_get_orbit_member_role: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)

    mock_delete_orbit.return_value = None
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_orbit_member_role.return_value = OrgRole.ADMIN

    deleted = await handler.delete_orbit(user_id, organization_id, orbit_id)

    assert deleted is None
    mock_delete_orbit.assert_awaited_once_with(orbit_id)


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.get_orbit_members",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_orbit_members(
    mock_get_orbit_members: AsyncMock,
    mock_get_orbit_member_role: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    organization_id = random.randint(1, 10000)
    expected = OrbitMember(**test_orbit_member)

    mock_get_orbit_members.return_value = expected
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_orbit_member_role.return_value = OrgRole.ADMIN

    result = await handler.get_orbit_members(
        expected.user.id, organization_id, expected.id
    )

    assert result == expected
    mock_get_orbit_members.assert_awaited_once_with(expected.id)


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.get_orbit_members_count",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.create_orbit_member",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_orbit_member(
    mock_create_orbit_member: AsyncMock,
    mock_get_orbit_members_count: AsyncMock,
    mock_get_orbit_member_role: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    organization_id = random.randint(1, 10000)
    expected = OrbitMember(**test_orbit_member)
    create_member = OrbitMemberCreate(
        user_id=test_orbit_member["user"]["id"],
        orbit_id=test_orbit_member["orbit_id"],
        role=test_orbit_member["role"],
    )

    mock_create_orbit_member.return_value = expected
    mock_get_orbit_members_count.return_value = 0
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_orbit_member_role.return_value = OrgRole.ADMIN

    result = await handler.create_orbit_member(
        test_orbit_member["user"]["id"], organization_id, create_member
    )

    assert result == expected
    mock_create_orbit_member.assert_awaited_once_with(create_member)


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.update_orbit_member",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_orbit_member(
    mock_update_orbit_member: AsyncMock,
    mock_get_orbit_member_role: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    organization_id = random.randint(1, 10000)
    expected = OrbitMember(**test_orbit_member)
    expected.role = OrbitRole.ADMIN
    update_member = UpdateOrbitMember(id=expected.id, role=OrbitRole.ADMIN)

    mock_update_orbit_member.return_value = expected
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_orbit_member_role.return_value = OrgRole.ADMIN

    result = await handler.update_orbit_member(
        expected.user.id, organization_id, expected.orbit_id, update_member
    )

    assert result == expected
    mock_update_orbit_member.assert_awaited_once_with(update_member)


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.update_orbit_member",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_orbit_member_not_found(
    mock_update_orbit_member: AsyncMock,
    mock_get_orbit_member_role: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)

    update_member = UpdateOrbitMember(id=random.randint(1, 10000), role=OrbitRole.ADMIN)

    mock_update_orbit_member.return_value = None
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_orbit_member_role.return_value = OrgRole.ADMIN

    with pytest.raises(NotFoundError, match="Orbit Member not found") as error:
        await handler.update_orbit_member(
            user_id, organization_id, orbit_id, update_member
        )

    assert error.value.status_code == 404
    mock_update_orbit_member.assert_awaited_once_with(update_member)


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.delete_orbit_member",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_orbit_member(
    mock_delete_orbit_member: AsyncMock,
    mock_get_orbit_member_role: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    user_id = random.randint(1, 10000)
    organization_id = random.randint(1, 10000)
    orbit_id = random.randint(1, 10000)
    member_id = random.randint(1, 10000)

    mock_delete_orbit_member.return_value = None
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_orbit_member_role.return_value = OrgRole.ADMIN

    deleted = await handler.delete_orbit_member(
        user_id, organization_id, orbit_id, member_id
    )

    assert deleted is None
    mock_delete_orbit_member.assert_awaited_once_with(member_id)
