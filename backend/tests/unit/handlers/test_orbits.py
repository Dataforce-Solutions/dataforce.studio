import datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from dataforce_studio.handlers.orbits import OrbitHandler
from dataforce_studio.infra.exceptions import NotFoundError
from dataforce_studio.schemas.orbit import (
    OrbitCreate,
    Orbit,
    OrbitDetails,
    OrbitUpdate,
    OrbitMember,
    OrbitMemberCreate,
    OrbitRole,
    UpdateOrbitMember,
)

handler = OrbitHandler()

test_orbit = {"name": "test", "organization_id": uuid4()}

test_orbit_created = {"id": uuid4(), "name": "test", "organization_id": uuid4()}

test_orbit_id = uuid4()

test_orbit_member = {
    "id": uuid4(),
    "orbit_id": test_orbit_id,
    "role": OrbitRole.MEMBER,
    "user": {
        "id": uuid4(),
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
    "organization_id": uuid4(),
    "members": [
        test_orbit_member,
    ],
    "created_at": datetime.datetime.now(),
    "updated_at": datetime.datetime.now(),
}


@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.create_orbit",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_organization_orbit(
    mock_create_orbit: AsyncMock,
) -> None:
    orbit_id = uuid4()
    orbit_to_create = OrbitCreate(**test_orbit)
    mocked_orbit = Orbit(**test_orbit, id=orbit_id)
    mock_create_orbit.return_value = mocked_orbit

    result = await handler.create_organization_orbit(orbit_to_create)

    assert result == mocked_orbit

    mock_create_orbit.assert_awaited_once_with(orbit_to_create)


@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.get_organization_orbits",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_organization_orbits(
    mock_get_organization_orbits: AsyncMock,
) -> None:
    orbit = Orbit(**test_orbit_created)
    expected = list(orbit)

    mock_get_organization_orbits.return_value = expected

    result = await handler.get_organization_orbits(orbit.organization_id)

    assert result == expected

    mock_get_organization_orbits.assert_awaited_once_with(orbit.organization_id)


@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.get_orbit",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_orbit(
    mock_get_orbit: AsyncMock,
) -> None:
    expected = OrbitDetails(**test_orbit_details)

    mock_get_orbit.return_value = expected

    result = await handler.get_orbit(expected.id)

    assert result == expected
    mock_get_orbit.assert_awaited_once_with(expected.id)


@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.get_orbit",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_orbit_not_found(
    mock_get_orbit: AsyncMock,
) -> None:
    orbit_id = uuid4()
    mock_get_orbit.return_value = None

    with pytest.raises(NotFoundError, match="Orbit not found") as error:
        await handler.get_orbit(orbit_id)

    assert error.value.status_code == 404
    mock_get_orbit.assert_awaited_once_with(orbit_id)


@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.update_orbit",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_orbit(
    mock_update_orbit: AsyncMock,
) -> None:
    expected = OrbitDetails(**test_orbit_details)
    mock_update_orbit.return_value = expected

    update_orbit = OrbitUpdate(id=expected.id, name="new_name")
    result = await handler.update_orbit(update_orbit)

    assert result == expected
    mock_update_orbit.assert_awaited_once_with(update_orbit)


@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.update_orbit",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_orbit_not_found(
    mock_update_orbit: AsyncMock,
) -> None:
    mock_update_orbit.return_value = None
    update_orbit = OrbitUpdate(id=uuid4(), name="new_name")

    with pytest.raises(NotFoundError, match="Orbit not found") as error:
        await handler.update_orbit(update_orbit)

    assert error.value.status_code == 404
    mock_update_orbit.assert_awaited_once_with(update_orbit)


@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.delete_orbit",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_orbit(
    mock_delete_orbit: AsyncMock,
) -> None:
    orbit_id = uuid4()
    mock_delete_orbit.return_value = None

    deleted = await handler.delete_orbit(orbit_id)

    assert deleted is None
    mock_delete_orbit.assert_awaited_once_with(orbit_id)


@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.get_orbit_members",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_orbit_members(
    mock_get_orbit_members: AsyncMock,
) -> None:
    expected = OrbitMember(**test_orbit_member)

    mock_get_orbit_members.return_value = expected

    result = await handler.get_orbit_members(expected.id)

    assert result == expected
    mock_get_orbit_members.assert_awaited_once_with(expected.id)


@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.create_orbit_member",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_orbit_member(
    mock_create_orbit_member: AsyncMock,
) -> None:
    expected = OrbitMember(**test_orbit_member)
    create_member = OrbitMemberCreate(
        user_id=test_orbit_member["user"]["id"],
        orbit_id=test_orbit_member["orbit_id"],
        role=test_orbit_member["role"],
    )
    mock_create_orbit_member.return_value = expected

    result = await handler.create_orbit_member(create_member)

    assert result == expected
    mock_create_orbit_member.assert_awaited_once_with(create_member)


@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.update_orbit_member",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_orbit_member(
    mock_update_orbit_member: AsyncMock,
) -> None:
    expected = OrbitMember(**test_orbit_member)
    expected.role = OrbitRole.ADMIN
    update_member = UpdateOrbitMember(id=expected.id, role=OrbitRole.ADMIN)
    mock_update_orbit_member.return_value = expected

    result = await handler.update_orbit_member(update_member)

    assert result == expected
    mock_update_orbit_member.assert_awaited_once_with(update_member)


@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.update_orbit_member",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_orbit_member_not_found(
    mock_update_orbit_member: AsyncMock,
) -> None:
    update_member = UpdateOrbitMember(id=uuid4(), role=OrbitRole.ADMIN)

    mock_update_orbit_member.return_value = None

    with pytest.raises(NotFoundError, match="Orbit Member not found") as error:
        await handler.update_orbit_member(update_member)

    assert error.value.status_code == 404
    mock_update_orbit_member.assert_awaited_once_with(update_member)


@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.delete_orbit_member",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_orbit_member(
    mock_delete_orbit_member: AsyncMock,
) -> None:
    member_id = uuid4()
    mock_delete_orbit_member.return_value = None

    deleted = await handler.delete_orbit_member(member_id)

    assert deleted is None
    mock_delete_orbit_member.assert_awaited_once_with(member_id)
