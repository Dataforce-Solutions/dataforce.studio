from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID

import pytest
from fastapi import Request
from luml.api.orbits.orbit_artifacts import create_artifact
from luml.schemas.artifacts import (
    ArtifactCreateIn,
    CreateArtifactResponse,
    LumlArtifactManifest,
)
from luml.schemas.lineage import LineageVia

USER_ID = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
ORGANIZATION_ID = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
ORBIT_ID = UUID("0199c337-09f3-753e-9def-b27745e69be6")
COLLECTION_ID = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
LINEAGE_INPUT_ID = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")


@pytest.mark.parametrize(
    ("scope", "via"),
    [("jwt", LineageVia.UI), ("api_key", LineageVia.API)],
)
@patch(
    "luml.handlers.artifacts.ArtifactHandler.create_artifact",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_artifact_route_forwards_inputs_and_creation_channel(
    mock_create_artifact: AsyncMock,
    scope: str,
    via: LineageVia,
) -> None:
    request = Mock(spec=Request)
    request.user = Mock(id=USER_ID)
    request.auth = Mock(scopes=["authenticated", scope])
    artifact = ArtifactCreateIn(
        file_name="model.luml",
        name="model",
        extra_values={},
        manifest=LumlArtifactManifest(
            artifact_type="model",
            variant="pipeline",
            producer_name="test",
            producer_version="1.0",
            producer_tags=[],
            payload={},
        ),
        file_hash="hash",
        file_index={},
        size=1,
        lineage_inputs=[LINEAGE_INPUT_ID],
    )
    expected = Mock(spec=CreateArtifactResponse)
    mock_create_artifact.return_value = expected

    result = await create_artifact(
        request,
        ORGANIZATION_ID,
        ORBIT_ID,
        COLLECTION_ID,
        artifact,
    )

    assert result is expected
    mock_create_artifact.assert_awaited_once_with(
        USER_ID,
        ORGANIZATION_ID,
        ORBIT_ID,
        COLLECTION_ID,
        artifact,
        via,
    )
