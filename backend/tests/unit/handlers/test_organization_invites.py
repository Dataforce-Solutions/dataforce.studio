import random
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from dataforce_studio.handlers.organizations import OrganizationHandler
from dataforce_studio.models import OrganizationInviteOrm
from dataforce_studio.schemas.organization import (
    CreateOrganizationInvite,
    OrganizationInvite,
    UserInvite,
)

from tests.conftest import (
    invite_accept_data,
    invite_data,
    invite_get_data,
    invite_user_get_data,
)

handler = OrganizationHandler()


@patch(
    "dataforce_studio.handlers.organizations.EmailHandler.send_organization_invite_email",
    new_callable=MagicMock,
)
@patch(
    "dataforce_studio.handlers.organizations.UserRepository.get_organization_members_count",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.organizations.InviteRepository.create_organization_invite",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_send_invite(
    mock_create_organization_invite: AsyncMock,
    mock_get_organization_members_count: AsyncMock,
    mock_send_organization_invite_email: MagicMock,
) -> None:
    invite = CreateOrganizationInvite(**invite_data)
    mocked_invite = OrganizationInviteOrm(**invite.model_dump())

    mock_get_organization_members_count.return_value = 0
    mock_create_organization_invite.return_value = mocked_invite

    result = await handler.send_invite(invite)

    assert result == mocked_invite

    mock_send_organization_invite_email.assert_called_once()
    mock_create_organization_invite.assert_awaited_once()
    # mock_create_organization_invite.assert_called_once_with(
    #     OrganizationInviteOrm(**invite.model_dump()))


@patch(
    "dataforce_studio.handlers.organizations.InviteRepository.delete_organization_invite",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_cancel_invite(
    mock_delete_organization_invite: AsyncMock,
) -> None:
    invite_id = random.randint(1, 10000)

    mock_delete_organization_invite.return_value = None

    result = await handler.cancel_invite(invite_id)

    assert result is None
    mock_delete_organization_invite.assert_awaited_once_with(invite_id)


@patch(
    "dataforce_studio.handlers.organizations.UserRepository.get_organization_members_count",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.organizations.UserRepository.create_organization_member",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.organizations.InviteRepository.get_invite",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.organizations.InviteRepository.delete_organization_invites_for_user",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_accept_invite(
    mock_delete_organization_invites_for_user: AsyncMock,
    mock_get_invite: AsyncMock,
    mock_create_organization_member: AsyncMock,
    mock_get_organization_members_count: AsyncMock,
) -> None:
    user_id = random.randint(1, 10000)
    invite = OrganizationInviteOrm(**invite_accept_data)

    mock_get_invite.return_value = invite
    mock_get_organization_members_count.return_value = 0

    result = await handler.accept_invite(invite.id, user_id)

    assert result is None
    mock_get_invite.assert_awaited_once_with(invite.id)
    mock_get_organization_members_count.assert_awaited_once_with(invite.organization_id)
    mock_create_organization_member.assert_awaited_once_with(
        user_id, invite.organization_id, invite.role
    )
    mock_delete_organization_invites_for_user.assert_awaited_once_with(
        invite.organization_id, invite.email
    )


@patch(
    "dataforce_studio.handlers.organizations.InviteRepository.delete_organization_invite",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_reject_invite(
    mock_delete_organization_invite: AsyncMock,
) -> None:
    invite_id = random.randint(1, 10000)

    mock_delete_organization_invite.return_value = None

    result = await handler.reject_invite(invite_id)

    assert result is None
    mock_delete_organization_invite.assert_awaited_once_with(invite_id)


@patch(
    "dataforce_studio.handlers.organizations.InviteRepository.get_invites_where",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_organization_invites(
    mock_get_organization_invites: AsyncMock,
) -> None:
    organization_id = random.randint(1, 10000)

    expected = [OrganizationInvite(**invite_get_data)]
    mock_get_organization_invites.return_value = expected

    actual = await handler.get_organization_invites(organization_id)

    assert actual == expected
    mock_get_organization_invites.assert_awaited_once()


@patch(
    "dataforce_studio.handlers.organizations.InviteRepository.get_invites_where",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_user_invites(
    mock_get_user_invites: AsyncMock,
) -> None:
    invite = UserInvite(**invite_user_get_data)
    expected = [invite]
    mock_get_user_invites.return_value = expected

    actual = await handler.get_user_invites(invite.email)

    assert actual == expected
    mock_get_user_invites.assert_awaited_once()
