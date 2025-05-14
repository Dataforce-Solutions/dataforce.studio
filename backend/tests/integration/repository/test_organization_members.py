import uuid

import pytest
import pytest_asyncio
from dataforce_studio.models.organization import OrgRole
from dataforce_studio.repositories.users import UserRepository
from dataforce_studio.schemas.organization import UpdateOrganizationMember
from dataforce_studio.schemas.user import AuthProvider, User
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import create_async_engine

organization_data = {"name": "test organization", "logo": None}

organization_member_data = {
    "user_id": "test organization",
    "organization_id": None,
    "role": None,
}


@pytest_asyncio.fixture(scope="function")
async def create_organization_with_members(
    create_database_and_apply_migrations: str,
) -> dict:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = UserRepository(engine)

    organization = await repo.create_organization(
        name="Test org with members", logo=None
    )

    members = []

    for i in range(10):
        user = User(
            email=f"user{i}@gmail.com",
            full_name=f"Test User {i}",
            disabled=False,
            email_verified=True,
            auth_method=AuthProvider.EMAIL,
            photo=None,
            hashed_password="hashed_password",
        )
        fetched_user = await repo.create_user(user)

        member = await repo.create_organization_member(
            user_id=fetched_user.id,
            organization_id=organization.id,
            role=OrgRole.MEMBER,
        )
        members.append(member)

    return {
        "engine": engine,
        "repo": repo,
        "organization": organization,
        "members": members,
    }


@pytest.mark.asyncio
async def test_create_organization_member(create_organization_with_user: dict) -> None:
    data = create_organization_with_user
    repo, user, created_organization = data["repo"], data["user"], data["organization"]

    created_member = await repo.create_organization_member(
        user.id, created_organization.id, OrgRole.MEMBER
    )

    assert created_member.id
    assert created_member.organization_id == created_organization.id
    assert created_member.user.id == user.id
    assert created_member.role == OrgRole.MEMBER


@pytest.mark.asyncio
async def test_create_organization_member_already_exist(
    create_organization_with_user: dict,
) -> None:
    data = create_organization_with_user
    repo, user, created_organization = data["repo"], data["user"], data["organization"]

    await repo.create_organization_member(
        user.id, created_organization.id, OrgRole.OWNER
    )

    with pytest.raises(HTTPException) as error:
        await repo.create_organization_member(
            user_id=user.id,
            organization_id=created_organization.id,
            role=OrgRole.ADMIN,
        )

    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_create_organization_server_error(
    create_organization_with_user: dict,
) -> None:
    data = create_organization_with_user
    repo, user, created_organization = data["repo"], data["user"], data["organization"]

    await repo.create_organization_member(
        user.id, created_organization.id, OrgRole.OWNER
    )

    with pytest.raises(HTTPException) as error:
        await repo.create_organization_member(
            user_id=str(uuid.uuid4()),
            organization_id=created_organization.id,
            role=OrgRole.ADMIN,
        )

    assert error.value.status_code == 500


@pytest.mark.asyncio
async def test_create_organization_owner(create_organization_with_user: dict) -> None:
    data = create_organization_with_user
    repo, user, created_organization = data["repo"], data["user"], data["organization"]

    created_member = await repo.create_owner(user.id, created_organization.id)

    assert created_member.id
    assert created_member.organization_id == created_organization.id
    assert created_member.role == OrgRole.OWNER
    assert created_member.user.id == user.id


@pytest.mark.asyncio
async def test_update_organization_member(create_organization_with_user: dict) -> None:
    data = create_organization_with_user
    repo, user, created_organization = data["repo"], data["user"], data["organization"]

    created_member = await repo.create_organization_member(
        user.id, created_organization.id, OrgRole.MEMBER
    )

    updated_member = await repo.update_organization_member(
        UpdateOrganizationMember(**{"id": created_member.id, "role": OrgRole.ADMIN})
    )

    assert updated_member.id == created_member.id
    assert updated_member.role == OrgRole.ADMIN


@pytest.mark.asyncio
async def test_delete_organization_member(create_organization_with_user: dict) -> None:
    data = create_organization_with_user
    repo, user, created_organization = data["repo"], data["user"], data["organization"]

    created_member = await repo.create_organization_member(
        user.id, created_organization.id, OrgRole.MEMBER
    )

    deleted_member = await repo.delete_organization_member(created_member.id)
    org_members_count = await repo.get_organization_members_count(
        created_organization.id
    )

    assert deleted_member is None
    assert org_members_count == 0 or org_members_count is None


@pytest.mark.asyncio
async def test_get_organization_members_count(
    create_organization_with_members: dict,
) -> None:
    data = create_organization_with_members
    repo, organization, members = (data["repo"], data["organization"], data["members"])

    count = await repo.get_organization_members_count(organization.id)

    assert len(members) == count


@pytest.mark.asyncio
async def test_get_organization_members(create_organization_with_members: dict) -> None:
    data = create_organization_with_members
    repo, organization, members = (data["repo"], data["organization"], data["members"])

    db_members = await repo.get_organization_members(organization.id)

    assert db_members
    assert len(members) == len(db_members)
    assert db_members[0].id
    assert db_members[0].organization_id == organization.id
    assert db_members[0].user.id
