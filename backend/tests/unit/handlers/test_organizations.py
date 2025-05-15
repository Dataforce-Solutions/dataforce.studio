import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from dataforce_studio.handlers.organizations import OrganizationHandler
from dataforce_studio.models import OrganizationInviteOrm
from dataforce_studio.models.errors import OrganizationLimitReachedError
from dataforce_studio.schemas.invite import CreateOrganizationInvite, OrganizationInvite
from dataforce_studio.schemas.organization import (
    OrganizationMember,
    OrganizationMemberCreate,
    OrgRole,
    UpdateOrganizationMember,
)

invite_data = {
    "email": "test@example.com",
    "role": OrgRole.MEMBER,
    "organization_id": uuid4(),
    "invited_by": uuid4(),
}

invite_get_data = {
    "id": uuid4(),
    "email": "test@example.com",
    "role": OrgRole.MEMBER,
    "organization_id": uuid4(),
    "invited_by": uuid4(),
    "created_at": datetime.datetime.now(),
}

invite_accept_data = {
    "id": uuid4(),
    "email": "test@example.com",
    "role": OrgRole.MEMBER,
    "organization_id": uuid4(),
    "invited_by": uuid4(),
}

member_data = {
    "id": uuid4(),
    "organization_id": uuid4(),
    "role": OrgRole.ADMIN,
    "user": {
        "id": uuid4(),
        "email": "test@gmail.com",
        "full_name": "Full Name",
        "disabled": False,
        "photo": None,
    },
}


handler = OrganizationHandler()


@patch(
    "dataforce_studio.handlers.organizations.UserRepository.get_organization_members_count",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_check_org_members_limit_raises(
    mock_get_organization_members_count: AsyncMock,
) -> None:
    mock_get_organization_members_count.return_value = 10

    with pytest.raises(
        OrganizationLimitReachedError,
        match="Organization reached maximum number of users",
    ):
        await handler.check_org_members_limit(organization_id=uuid4(), num=1)

    mock_get_organization_members_count.assert_awaited_once()


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
    invite_id = uuid4()

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
    user_id = uuid4()
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
    invite_id = uuid4()

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
    organization_id = uuid4()

    expected = list(OrganizationInvite(**invite_get_data))
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
    expected = list(OrganizationInvite(**invite_get_data))
    mock_get_user_invites.return_value = expected

    actual = await handler.get_user_invites(invite_get_data["email"])

    assert actual == expected
    mock_get_user_invites.assert_awaited_once()


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

    update_member = UpdateOrganizationMember(
        id=member_data["id"], role=member_data["role"]
    )
    actual = await handler.update_organization_member_by_id(update_member)

    assert actual == expected
    mock_update_organization_member.assert_awaited_once_with(update_member)


@patch(
    "dataforce_studio.handlers.organizations.UserRepository.delete_organization_member",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_organization_member_by_id(
    mock_delete_organization_member: AsyncMock,
) -> None:
    member_id = uuid4()
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
