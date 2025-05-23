import random
from unittest.mock import AsyncMock, patch

import pytest
from dataforce_studio.handlers.organizations import OrganizationHandler
from dataforce_studio.schemas.organization import (
    OrganizationMember,
    OrganizationMemberCreate,
    UpdateOrganizationMember,
)

from tests.conftest import member_data

handler = OrganizationHandler()


@patch(
    "dataforce_studio.handlers.organizations.UserRepository.get_organization_members",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_organization_members_data(
    mock_get_organization_members: AsyncMock,
) -> None:
    expected = list(OrganizationMember(**member_data))
    mock_get_organization_members.return_value = expected

    actual = await handler.get_organization_members_data(member_data["organization_id"])

    assert actual == expected
    mock_get_organization_members.assert_awaited_once()


@patch(
    "dataforce_studio.handlers.organizations.UserRepository.update_organization_member",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_organization_member_by_id(
    mock_update_organization_member: AsyncMock,
) -> None:
    expected = OrganizationMember(**member_data)
    mock_update_organization_member.return_value = expected

    update_member = UpdateOrganizationMember(role=member_data["role"])
    actual = await handler.update_organization_member_by_id(
        member_data["id"], update_member
    )

    assert actual == expected
    mock_update_organization_member.assert_awaited_once()


@patch(
    "dataforce_studio.handlers.organizations.UserRepository.delete_organization_member",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_organization_member_by_id(
    mock_delete_organization_member: AsyncMock,
) -> None:
    member_id = random.randint(1, 10000)
    mock_delete_organization_member.return_value = None

    actual = await handler.delete_organization_member_by_id(member_id)

    assert actual is None
    mock_delete_organization_member.assert_awaited_once_with(member_id)


@patch(
    "dataforce_studio.handlers.organizations.UserRepository.create_organization_member",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_add_organization_member(
    mock_create_organization_member: AsyncMock,
) -> None:
    member_create = OrganizationMemberCreate(
        **{
            "user_id": member_data["user"]["id"],
            "organization_id": member_data["organization_id"],
            "role": member_data["role"],
        }
    )
    expected = OrganizationMember(**member_data)
    mock_create_organization_member.return_value = expected

    actual = await handler.add_organization_member(member_create)

    assert actual == expected
    mock_create_organization_member.assert_awaited_once_with(
        member_create.user_id, member_create.organization_id, member_create.role
    )
