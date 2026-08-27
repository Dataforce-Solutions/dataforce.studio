from typing import cast
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID

import pytest
from luml.api.orbits.orbit_satellites import get_satellite_openapi
from starlette.requests import Request


@patch(
    "luml.api.orbits.orbit_satellites.SatelliteHandler.get_satellite_openapi",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_satellite_openapi_endpoint(
    mock_get_satellite_openapi: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")
    document = {"openapi": "3.1.0", "paths": {}}
    request = Mock(user=Mock(id=user_id))
    mock_get_satellite_openapi.return_value = document

    result = await get_satellite_openapi(
        cast(Request, request), organization_id, orbit_id, satellite_id
    )

    assert result == document
    mock_get_satellite_openapi.assert_awaited_once_with(
        user_id, organization_id, orbit_id, satellite_id
    )
