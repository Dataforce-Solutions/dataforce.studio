import pytest
from dataforce_studio.repositories.users import UserRepository
from sqlalchemy.ext.asyncio import create_async_engine


organization_data = {
    'name': 'test organization name',
    'logo': None
}


@pytest.mark.asyncio
async def test_create_organization(create_database_and_apply_migrations: str) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = UserRepository(engine)

    created_organization = await repo.create_organization(organization_data['name'], organization_data['logo'])

    assert created_organization.id
    assert created_organization.name == organization_data['name']
    assert created_organization.logo == organization_data['logo']

