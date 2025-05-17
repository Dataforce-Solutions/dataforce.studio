import pytest
from dataforce_studio.repositories.users import UserRepository
from sqlalchemy.ext.asyncio import create_async_engine

organization_data = {"name": "test organization name", "logo": None}


@pytest.mark.asyncio
async def test_create_organization(create_database_and_apply_migrations: str) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = UserRepository(engine)

    created_organization = await repo.create_organization(
        organization_data["name"], organization_data["logo"]
    )

    assert created_organization.id
    assert created_organization.name == organization_data["name"]
    assert created_organization.logo == organization_data["logo"]


@pytest.mark.asyncio
async def test_get_user_organizations(create_organization_with_members: dict) -> None:
    data = create_organization_with_members
    repo, members = data["repo"], data["members"]

    user_id = members[0].user.id
    organizations = await repo.get_user_organizations(user_id)

    assert organizations
    assert hasattr(organizations[0], "id")
    assert hasattr(organizations[0], "name")
    assert hasattr(organizations[0], "logo")
    assert hasattr(organizations[0], "role")


@pytest.mark.asyncio
async def test_get_organization_details(create_organization_with_members: dict) -> None:
    data = create_organization_with_members
    repo, org = data["repo"], data["organization"]

    organization = await repo.get_organization_details(org.id)

    assert organization
    assert hasattr(organization, "id")
    assert hasattr(organization, "name")
    assert hasattr(organization, "logo")
    assert isinstance(organization.members, list)
    assert isinstance(organization.invites, list)
