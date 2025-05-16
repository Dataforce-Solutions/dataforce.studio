from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from dataforce_studio.handlers.organizations import OrganizationHandler
from dataforce_studio.infra.exceptions import OrganizationLimitReachedError
from dataforce_studio.models.errors import OrganizationNotFoundError
from dataforce_studio.schemas.organization import (
    OrganizationDetails,
    OrganizationSwitcher,
    OrgRole,
)

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
    "dataforce_studio.handlers.organizations.UserRepository.get_user_organizations",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_user_organizations(
    mock_get_user_organizations: AsyncMock, test_org: dict
) -> None:
    user_id = uuid4()
    expected = [OrganizationSwitcher(**test_org, role=OrgRole.MEMBER)]
    mock_get_user_organizations.return_value = expected

    actual = await handler.get_user_organizations(user_id)

    assert actual == expected
    mock_get_user_organizations.assert_awaited_once_with(user_id)


@patch(
    "dataforce_studio.handlers.organizations.UserRepository.get_organization_details",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_organization(
    mock_get_organization_details: AsyncMock, test_org_details: dict
) -> None:
    organization_id = uuid4()
    expected = OrganizationDetails(**test_org_details)
    mock_get_organization_details.return_value = expected

    actual = await handler.get_organization(organization_id)

    assert actual
    mock_get_organization_details.assert_awaited_once_with(organization_id)


@patch(
    "dataforce_studio.handlers.organizations.UserRepository.get_organization_details",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_organization_not_found(
    mock_get_organization_details: AsyncMock,
) -> None:
    organization_id = uuid4()
    mock_get_organization_details.return_value = None

    with pytest.raises(
        OrganizationNotFoundError,
        match="Organization not found",
    ):
        await handler.get_organization(organization_id)

    mock_get_organization_details.assert_awaited_once_with(organization_id)
