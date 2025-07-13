import pytest
from dataforce_studio.schemas.user import CreateUser, AuthProvider
from dataforce_studio.schemas.organization import (
    OrgRole,
    UpdateOrganizationMember,
    OrganizationMemberCreate,
)

organization_data = {"name": "test organization", "logo": None}

organization_member_data = {
    "user_id": "test organization",
    "organization_id": None,
    "role": None,
}


@pytest.mark.asyncio
async def test_create_organization_member(create_organization_with_user: dict) -> None:
    data = create_organization_with_user
    repo, created_organization = data["repo"], data["organization"]

    create_user = CreateUser(
        email="test@test.com",
        full_name="Test User",
        disabled=False,
        email_verified=True,
        auth_method=AuthProvider.EMAIL,
        photo=None,
        hashed_password="hashed_password",
    )
    user = await repo.create_user(create_user)
    created_member = await repo.create_organization_member(
        OrganizationMemberCreate(
            user_id=user.id,
            organization_id=created_organization.id,
            role=OrgRole.MEMBER,
        )
    )

    assert created_member.id
    assert created_member.organization_id == created_organization.id
    assert created_member.user.id == user.id
    assert created_member.role == OrgRole.MEMBER


@pytest.mark.asyncio
async def test_update_organization_member(create_organization_with_user: dict) -> None:
    data = create_organization_with_user
    repo, member = data["repo"], data["member"]

    updated_member = await repo.update_organization_member(
        member.id, UpdateOrganizationMember(role=OrgRole.ADMIN)
    )

    assert updated_member.id == member.id
    assert updated_member.role == OrgRole.ADMIN


@pytest.mark.asyncio
async def test_delete_organization_member(create_organization_with_user: dict) -> None:
    data = create_organization_with_user
    repo, created_organization, member = (
        data["repo"],
        data["organization"],
        data["member"],
    )

    deleted_member = await repo.delete_organization_member(member.id)
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
