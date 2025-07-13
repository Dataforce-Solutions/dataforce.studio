from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dataforce_studio.handlers.organizations import OrganizationHandler
from dataforce_studio.infra.exceptions import ServiceError
from dataforce_studio.models import OrganizationInviteOrm
from dataforce_studio.schemas.organization import (
    CreateOrganizationInviteIn,
    Organization,
    OrganizationInvite,
    OrganizationMemberCreate,
    OrgRole,
    UserInvite,
)
from dataforce_studio.schemas.user import UserOut

handler = OrganizationHandler()


@patch(
    "dataforce_studio.handlers.organizations.InviteRepository.get_organization_invite_by_email",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.organizations.UserRepository.get_organization_member_by_email",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.organizations.UserRepository.get_public_user_by_id",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.organizations.InviteRepository.get_invite",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
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
    mock_get_organization_member_role: AsyncMock,
    mock_get_invite: AsyncMock,
    mock_get_public_user_by_id: AsyncMock,
    mock_get_organization_member_by_email: AsyncMock,
    mock_get_organization_invite_by_email: AsyncMock,
) -> None:
    user_id = 1
    invite_id = 100
    organization_id = 10

    user = UserOut(
        id=user_id,
        email="testuser@example.com",
        full_name="Test User",
        disabled=False,
        photo=None,
    )

    invite = CreateOrganizationInviteIn(
        email="test@example.com",
        role=OrgRole.MEMBER,
        organization_id=organization_id,
    )
    mocked_invite = OrganizationInvite(
        id=invite_id,
        email="test@example.com",
        role=OrgRole.MEMBER,
        organization_id=organization_id,
        created_at=datetime.now(),
    )

    mock_get_organization_invite_by_email.return_value = None
    mock_get_organization_member_by_email.return_value = None
    mock_get_organization_members_count.return_value = 0
    mock_get_public_user_by_id.return_value = user
    mock_create_organization_invite.return_value = mocked_invite
    mock_get_invite.return_value = mocked_invite
    mock_get_organization_member_role.return_value = OrgRole.OWNER

    result = await handler.send_invite(user_id, invite)

    assert result == mocked_invite

    mock_send_organization_invite_email.assert_called_once()
    mock_create_organization_invite.assert_awaited_once()


@patch(
    "dataforce_studio.handlers.organizations.UserRepository.get_public_user_by_id",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_send_invite_to_yourself(
    mock_get_organization_member_role: AsyncMock,
    mock_get_public_user_by_id: AsyncMock,
) -> None:
    user_id = 1
    organization_id = 10

    user = UserOut(
        id=user_id,
        email="test@test.com",
        full_name="Test User",
        disabled=False,
        photo=None,
    )

    invite = CreateOrganizationInviteIn(
        email=user.email,
        role=OrgRole.MEMBER,
        organization_id=organization_id,
    )

    mock_get_public_user_by_id.return_value = user
    mock_get_organization_member_role.return_value = OrgRole.OWNER

    with pytest.raises(ServiceError, match="You can't invite yourself"):
        await handler.send_invite(user_id, invite)


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.organizations.InviteRepository.delete_organization_invite",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_cancel_invite(
    mock_delete_organization_invite: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    user_id = 1
    organization_id = 10
    invite_id = 100

    mock_delete_organization_invite.return_value = None
    mock_get_organization_member_role.return_value = OrgRole.OWNER

    result = await handler.cancel_invite(user_id, organization_id, invite_id)

    assert result is None
    mock_delete_organization_invite.assert_awaited_once_with(invite_id)


@patch(
    "dataforce_studio.handlers.organizations.UserRepository.get_user_organizations_membership_count",
    new_callable=AsyncMock,
)
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
    mock_get_user_organizations_membership_count: AsyncMock,
) -> None:
    user_id = 1
    invite_id = 100
    organization_id = 10
    invited_by_id = 2

    invite = OrganizationInviteOrm(
        id=invite_id,
        email="test@example.com",
        role=OrgRole.MEMBER,
        organization_id=organization_id,
        invited_by=invited_by_id,
    )

    mock_get_invite.return_value = invite
    mock_get_organization_members_count.return_value = 0
    mock_get_user_organizations_membership_count.return_value = 0

    result = await handler.accept_invite(invite.id, user_id)

    assert result is None
    mock_get_invite.assert_awaited_once_with(invite.id)
    mock_get_organization_members_count.assert_awaited_once_with(invite.organization_id)
    mock_create_organization_member.assert_awaited_once_with(
        OrganizationMemberCreate(
            user_id=user_id,
            organization_id=invite.organization_id,
            role=OrgRole(invite.role),
        )
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
    invite_id = 100

    mock_delete_organization_invite.return_value = None

    result = await handler.reject_invite(invite_id)

    assert result is None
    mock_delete_organization_invite.assert_awaited_once_with(invite_id)


@patch(
    "dataforce_studio.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.organizations.InviteRepository.get_invites_by_organization_id",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_organization_invites(
    mock_get_organization_invites: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    user_id = 1
    organization_id = 10

    expected = [
        OrganizationInvite(
            id=100,
            email="test@example.com",
            role=OrgRole.MEMBER,
            organization_id=organization_id,
            invited_by_user=UserOut(
                id=2,
                email="inviter@example.com",
                full_name="Inviter User",
                disabled=False,
                photo=None,
            ),
            created_at=datetime.now(),
        )
    ]

    mock_get_organization_invites.return_value = expected
    mock_get_organization_member_role.return_value = OrgRole.OWNER

    actual = await handler.get_organization_invites(user_id, organization_id)

    assert actual == expected
    mock_get_organization_invites.assert_awaited_once()


@patch(
    "dataforce_studio.handlers.organizations.InviteRepository.get_invites_by_user_email",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_user_invites(
    mock_get_user_invites: AsyncMock,
) -> None:
    user_email = "test@example.com"
    organization_id = 10

    invite = UserInvite(
        id=100,
        email=user_email,
        role=OrgRole.MEMBER,
        organization_id=organization_id,
        invited_by_user=UserOut(
            id=2,
            email="inviter@example.com",
            full_name="Inviter User",
            disabled=False,
            photo=None,
        ),
        created_at=datetime.now(),
        organization=Organization(
            id=organization_id,
            name="Test Organization",
            logo=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        ),
    )
    expected = [invite]
    mock_get_user_invites.return_value = expected

    actual = await handler.get_user_invites(user_email)

    assert actual == expected
    mock_get_user_invites.assert_awaited_once()
