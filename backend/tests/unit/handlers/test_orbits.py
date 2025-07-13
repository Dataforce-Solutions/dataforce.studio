from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from dataforce_studio.handlers.orbits import OrbitHandler
from dataforce_studio.models import OrganizationMemberOrm
from dataforce_studio.infra.exceptions import (
    NotFoundError,
)
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
from dataforce_studio.schemas.organization import OrgRole
from dataforce_studio.schemas.user import UserOut

handler = OrbitHandler()


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
@patch(
    "dataforce_studio.handlers.orbits.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_organization_orbit(
    mock_get_bucket_secret: AsyncMock,
    mock_create_orbit: AsyncMock,
    mock_get_organization_orbits_count: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    organization_id = 1
    bucket_secret_id = 1
    orbit_id = 1
    user_id = 1

    mock_get_bucket_secret.return_value = type(
        "obj",
        (),
        {
            "id": orbit_id,
            "organization_id": organization_id,
            "name": "test_secret",
        },
    )
    orbit_to_create = OrbitCreateIn(
        name="test",
        bucket_secret_id=bucket_secret_id,
    )
    mocked_orbit = Orbit(
        id=orbit_id,
        name="test",
        organization_id=organization_id,
        bucket_secret_id=bucket_secret_id,
        total_members=0,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    mock_create_orbit.return_value = mocked_orbit
    mock_get_organization_orbits_count.return_value = 0
    mock_get_organization_member_role.return_value = OrgRole.OWNER

    result = await handler.create_organization_orbit(
        user_id, mocked_orbit.organization_id, orbit_to_create
    )

    assert result == mocked_orbit

    mock_create_orbit.assert_awaited_once_with(
        mocked_orbit.organization_id, orbit_to_create
    )


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbits.BucketSecretRepository.get_bucket_secret",
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
async def test_create_organization_orbit_secret_not_found(
    mock_create_orbit: AsyncMock,
    mock_get_orbits_count: AsyncMock,
    mock_get_secret: AsyncMock,
    mock_get_org_role: AsyncMock,
) -> None:
    user_id = 1
    bucket_secret_id = 1
    organization_id = 1

    orbit_to_create = OrbitCreateIn(name="test", bucket_secret_id=bucket_secret_id)

    mock_get_orbits_count.return_value = 0
    mock_get_secret.return_value = None
    mock_get_org_role.return_value = OrgRole.OWNER

    with pytest.raises(NotFoundError, match="Bucket secret not found") as error:
        await handler.create_organization_orbit(
            user_id, organization_id, orbit_to_create
        )

    assert error.value.status_code == 404
    mock_create_orbit.assert_not_called()


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.orbits.BucketSecretRepository.get_bucket_secret",
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
async def test_create_organization_orbit_secret_wrong_org(
    mock_create_orbit: AsyncMock,
    mock_get_orbits_count: AsyncMock,
    mock_get_secret: AsyncMock,
    mock_get_org_role: AsyncMock,
) -> None:
    user_id = 1
    bucket_secret_id = 1
    organization_id = 1

    orbit_to_create = OrbitCreateIn(name="test", bucket_secret_id=bucket_secret_id)

    class Secret:
        def __init__(self, organization_id: int) -> None:
            self.organization_id = organization_id

    mock_get_orbits_count.return_value = 0
    mock_get_secret.return_value = Secret(organization_id + 1)
    mock_get_org_role.return_value = OrgRole.OWNER

    with pytest.raises(NotFoundError, match="Bucket secret not found") as error:
        await handler.create_organization_orbit(
            user_id, organization_id, orbit_to_create
        )

    assert error.value.status_code == 404
    mock_create_orbit.assert_not_called()


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
    user_id = 1

    orbit = Orbit(
        id=1,
        name="test",
        organization_id=1,
        bucket_secret_id=1,
        total_members=0,
        created_at=datetime.now(),
    )
    expected = [orbit]

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
    user_id = 1
    expected = OrbitDetails(
        id=1,
        name="test",
        organization_id=1,
        bucket_secret_id=1,
        members=None,
        created_at=datetime.now(),
    )

    mock_get_orbit.return_value = expected
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_orbit_member_role.return_value = OrgRole.ADMIN

    result = await handler.get_orbit(user_id, expected.organization_id, expected.id)

    assert result == expected
    mock_get_orbit.assert_awaited_once_with(expected.id, expected.organization_id)


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
    user_id = 1
    organization_id = 1
    orbit_id = 1

    mock_get_orbit.return_value = None
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_orbit_member_role.return_value = OrgRole.ADMIN

    with pytest.raises(NotFoundError, match="Orbit not found") as error:
        await handler.get_orbit(user_id, organization_id, orbit_id)

    assert error.value.status_code == 404
    mock_get_orbit.assert_awaited_once_with(orbit_id, organization_id)


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
    user_id = 1
    expected = OrbitDetails(
        id=1,
        name="test",
        organization_id=1,
        bucket_secret_id=1,
        members=None,
        created_at=datetime.now(),
    )

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
    user_id = 1
    organization_id = 1
    orbit_id = 1
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
    user_id = 1
    organization_id = 1
    orbit_id = 1

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
    organization_id = 1
    expected = OrbitMember(
        id=8766,
        orbit_id=1,
        role=OrbitRole.MEMBER,
        user=UserOut(
            id=5566,
            email="brandihernandez@example.org",
            full_name="Kathy Hall",
            disabled=False,
            photo=None,
        ),
        created_at=datetime.now(),
    )

    mock_get_orbit_members.return_value = expected
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_orbit_member_role.return_value = OrgRole.ADMIN

    result = await handler.get_orbit_members(
        expected.user.id, organization_id, expected.id
    )

    assert result == expected
    mock_get_orbit_members.assert_awaited_once_with(expected.id)


@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.emails.EmailHandler.send_added_to_orbit_email",
    new_callable=MagicMock,
)
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
@patch(
    "dataforce_studio.handlers.orbits.UserRepository.get_organization_member",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_orbit_member(
    mock_get_organization_member: AsyncMock,
    mock_create_orbit_member: AsyncMock,
    mock_get_orbit_members_count: AsyncMock,
    mock_get_orbit_member_role: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    mock_send_added_to_orbit_email: MagicMock,
    mock_get_orbit_simple: AsyncMock,
) -> None:
    current_user_id = 1
    organization_id = 1
    orbit_id = 1
    user_id = 5566
    member_id = 8766

    expected = OrbitMember(
        id=8766,
        orbit_id=orbit_id,
        role=OrbitRole.MEMBER,
        user=UserOut(
            id=user_id,
            email="brandihernandez@example.org",
            full_name="Kathy Hall",
            disabled=False,
            photo=None,
        ),
        created_at=datetime.now(),
    )
    create_member = OrbitMemberCreate(
        user_id=user_id,
        orbit_id=orbit_id,
        role=OrbitRole.MEMBER,
    )

    mock_get_organization_member.return_value = OrganizationMemberOrm(
        id=member_id,
        user_id=user_id,
        organization_id=organization_id,
        role=OrgRole.OWNER,
    )
    mock_create_orbit_member.return_value = expected
    mock_get_orbit_members_count.return_value = 0
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_orbit_member_role.return_value = OrgRole.ADMIN
    mock_get_orbit_simple.return_value = type(
        "obj",
        (),
        {"bucket_secret_id": 1, "organization_id": organization_id, "name": "name"},
    )

    result = await handler.create_orbit_member(
        current_user_id, organization_id, create_member
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
@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.get_orbit_member",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_orbit_member(
    mock_get_orbit_member: AsyncMock,
    mock_update_orbit_member: AsyncMock,
    mock_get_orbit_member_role: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    user_id = 1
    organization_id = 1

    expected = OrbitMember(
        id=8766,
        orbit_id=1,
        role=OrbitRole.MEMBER,
        user=UserOut(
            id=5566,
            email="brandihernandez@example.org",
            full_name="Kathy Hall",
            disabled=False,
            photo=None,
        ),
        created_at=datetime.now(),
    )
    expected.role = OrbitRole.ADMIN
    update_member = UpdateOrbitMember(id=expected.id, role=OrbitRole.ADMIN)

    mock_get_orbit_member.return_value = expected
    mock_update_orbit_member.return_value = expected
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_orbit_member_role.return_value = OrgRole.ADMIN

    result = await handler.update_orbit_member(
        user_id, organization_id, expected.orbit_id, update_member
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
@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.get_orbit_member",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_orbit_member_not_found(
    mock_get_orbit_member: AsyncMock,
    mock_update_orbit_member: AsyncMock,
    mock_get_orbit_member_role: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    user_id = 1
    organization_id = 1
    orbit_id = 1

    update_member = UpdateOrbitMember(id=1, role=OrbitRole.ADMIN)

    mock_get_orbit_member.return_value = None
    mock_update_orbit_member.return_value = None
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_orbit_member_role.return_value = OrgRole.ADMIN

    with pytest.raises(NotFoundError, match="Orbit Member not found") as error:
        await handler.update_orbit_member(
            user_id, organization_id, orbit_id, update_member
        )

    assert error.value.status_code == 404


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
@patch(
    "dataforce_studio.handlers.orbits.OrbitRepository.get_orbit_member",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_orbit_member(
    mock_get_orbit_member: AsyncMock,
    mock_delete_orbit_member: AsyncMock,
    mock_get_orbit_member_role: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    current_user_id = 1
    organization_id = 1

    member = OrbitMember(
        id=8766,
        orbit_id=1,
        role=OrbitRole.MEMBER,
        user=UserOut(
            id=5566,
            email="brandihernandez@example.org",
            full_name="Kathy Hall",
            disabled=False,
            photo=None,
        ),
        created_at=datetime.now(),
    )

    mock_get_orbit_member.return_value = member
    mock_delete_orbit_member.return_value = None
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_orbit_member_role.return_value = OrgRole.ADMIN

    deleted = await handler.delete_orbit_member(
        current_user_id, organization_id, member.orbit_id, member.id
    )

    assert deleted is None
    mock_delete_orbit_member.assert_awaited_once_with(member.id)
