import uuid

import pytest
from dataforce_studio.models.organization import (
    DBOrganization,
    DBOrganizationInvite,
    OrgRole,
)
from dataforce_studio.repositories.invites import InviteRepository
from dataforce_studio.schemas.user import User
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import create_async_engine


def get_invite_obj(organization: DBOrganization, user: User) -> DBOrganizationInvite:
    return DBOrganizationInvite(
        **{
            "email": "test@gmail.com",
            "role": OrgRole.MEMBER,
            "organization_id": organization.id,
            "invited_by": user.id,
        }
    )


@pytest.mark.asyncio
async def test_create_organization_invite(create_organization_with_user: dict) -> None:
    data = create_organization_with_user
    engine, user, organization = data["engine"], data["user"], data["organization"]
    repo = InviteRepository(engine)

    invite = get_invite_obj(organization, user)

    created_invite = await repo.create_organization_invite(invite)

    assert created_invite.id == invite.id
    assert created_invite.email == invite.email
    assert created_invite.organization_id == invite.organization_id


@pytest.mark.asyncio
async def test_delete_organization_invite(create_organization_with_user: dict) -> None:
    data = create_organization_with_user
    engine, user, organization = data["engine"], data["user"], data["organization"]
    repo = InviteRepository(engine)

    invite = get_invite_obj(organization, user)

    created_invite = await repo.create_organization_invite(invite)

    deleted_invite = await repo.delete_organization_invite(created_invite.id)

    assert deleted_invite is None


@pytest.mark.asyncio
async def test_delete_organization_invite_not_found(
    create_database_and_apply_migrations: str, test_user: dict
) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = InviteRepository(engine)

    with pytest.raises(HTTPException) as error:
        await repo.delete_organization_invite(uuid.uuid4())

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_get_invite(create_organization_with_user: dict) -> None:
    data = create_organization_with_user
    engine, user, organization = data["engine"], data["user"], data["organization"]
    repo = InviteRepository(engine)

    created_invite = await repo.create_organization_invite(
        get_invite_obj(organization, user)
    )
    fetched_invite = await repo.get_invite(created_invite.id)

    assert fetched_invite.id == created_invite.id
    assert fetched_invite.email == created_invite.email
    assert fetched_invite.invited_by == created_invite.invited_by
    assert fetched_invite.organization_id == created_invite.organization_id


@pytest.mark.asyncio
async def test_get_invite_not_found(
    create_database_and_apply_migrations: str, test_user: dict
) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = InviteRepository(engine)

    with pytest.raises(HTTPException) as error:
        await repo.get_invite(uuid.uuid4())

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_get_invite_where(create_organization_with_user: dict) -> None:
    data = create_organization_with_user
    engine, user, organization = data["engine"], data["user"], data["organization"]
    repo = InviteRepository(engine)

    for i in range(4):
        invite_i = get_invite_obj(organization, user)
        invite_i.email = f"{i}_{invite_i.email}"
        await repo.create_organization_invite(invite_i)

    invites = await repo.get_invites_where(
        DBOrganizationInvite.organization_id == organization.id
    )

    assert isinstance(invites, list)
    assert len(invites) == 4
    assert invites[0].organization_id == organization.id


@pytest.mark.asyncio
async def test_delete_invite_where(create_organization_with_user: dict) -> None:
    data = create_organization_with_user
    engine, user, organization = data["engine"], data["user"], data["organization"]
    repo = InviteRepository(engine)

    for i in range(4):
        invite_i = get_invite_obj(organization, user)
        invite_i.email = f"{i}_{invite_i.email}"
        await repo.create_organization_invite(invite_i)

    deleted_invites = await repo.delete_organization_invites_where(
        DBOrganizationInvite.organization_id == organization.id
    )

    invites = await repo.get_invites_where(
        DBOrganizationInvite.organization_id == organization.id
    )

    assert deleted_invites is None
    assert len(invites) == 0
