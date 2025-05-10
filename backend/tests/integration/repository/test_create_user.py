import pytest
from dataforce_studio.models.organization import OrgRole
from dataforce_studio.models.user import AuthProvider, CreateUser
from dataforce_studio.repositories.users import UserRepository
from dataforce_studio.schemas.user import AuthProvider, User
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.asyncio
async def test_create_user_and_organization(
    create_database_and_apply_migrations: str
) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = UserRepository(engine)
    user = CreateUser(
        email="test@email.com",
        full_name="Test User",
        disabled=False,
        email_verified=True,
        auth_method=AuthProvider.EMAIL,
        photo=None,
        hashed_password="hashed_password",
    )

    created_user = await repo.create_user(user)
    fetched_user = await repo.get_user(user.email)
    fetched_org = (await repo.get_user_organizations(fetched_user.id, OrgRole.OWNER))[0]
    fetched_org_member = (
        await repo.get_organization_users(fetched_org.id, OrgRole.OWNER)
    )[0]

    assert fetched_org.name == "Test's organization"
    assert fetched_org_member.user_id == created_user.id
    assert fetched_org_member.organization_id == fetched_org.id
    assert created_user == fetched_user
