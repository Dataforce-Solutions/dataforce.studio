from unittest.mock import AsyncMock, patch
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient
from luml.api.orbits.orbit_collections import collections_router
from luml.api.orbits.orbit_tracks import tracks_router
from luml.models import AuthUser
from luml.schemas.collections import (
    CollectionsList,
    CollectionSortBy,
    CollectionTypeFilter,
)
from luml.schemas.general import SortOrder
from luml.schemas.tracks import TracksList, TrackSortBy
from starlette.authentication import AuthCredentials, AuthenticationBackend
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.requests import HTTPConnection

USER_ID = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
ORG_ID = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
ORBIT_ID = UUID("0199c337-09f3-753e-9def-b27745e69be6")


class StubAuthBackend(AuthenticationBackend):
    async def authenticate(
        self, conn: HTTPConnection
    ) -> tuple[AuthCredentials, AuthUser]:
        return (
            AuthCredentials(["authenticated", "jwt"]),
            AuthUser(user_id=USER_ID, email="test@example.com"),
        )


def create_test_client() -> TestClient:
    app = FastAPI()
    app.include_router(collections_router, prefix="/v1/organizations")
    app.include_router(tracks_router, prefix="/v1/organizations")
    app.add_middleware(AuthenticationMiddleware, backend=StubAuthBackend())
    return TestClient(app)


@patch(
    "luml.handlers.collections.CollectionHandler.get_orbit_collections",
    new_callable=AsyncMock,
)
def test_get_orbit_collections_repeated_tags_and_types(
    mock_get_collections: AsyncMock,
) -> None:
    mock_get_collections.return_value = CollectionsList(items=[], cursor=None)
    client = create_test_client()

    response = client.get(
        f"/v1/organizations/{ORG_ID}/orbits/{ORBIT_ID}/collections",
        params=[("tags", "production"), ("tags", "ml"), ("types", "model")],
    )

    assert response.status_code == 200
    assert response.json() == {"items": [], "cursor": None}
    mock_get_collections.assert_awaited_once_with(
        USER_ID,
        ORG_ID,
        ORBIT_ID,
        None,
        50,
        CollectionSortBy.CREATED_AT,
        SortOrder.DESC,
        None,
        [CollectionTypeFilter.MODEL],
        ["production", "ml"],
    )


@patch(
    "luml.handlers.collections.CollectionHandler.get_orbit_collections_tags",
    new_callable=AsyncMock,
)
def test_get_orbit_collections_tags(mock_get_tags: AsyncMock) -> None:
    mock_get_tags.return_value = ["ml", "production", "staging"]
    client = create_test_client()

    response = client.get(
        f"/v1/organizations/{ORG_ID}/orbits/{ORBIT_ID}/collections/tags"
    )

    assert response.status_code == 200
    assert response.json() == ["ml", "production", "staging"]
    mock_get_tags.assert_awaited_once_with(USER_ID, ORG_ID, ORBIT_ID)


@patch(
    "luml.handlers.tracks.TracksHandler.list_tracks",
    new_callable=AsyncMock,
)
def test_list_tracks_repeated_tags_and_types(mock_list_tracks: AsyncMock) -> None:
    mock_list_tracks.return_value = TracksList(items=[], cursor=None)
    client = create_test_client()

    response = client.get(
        f"/v1/organizations/{ORG_ID}/orbits/{ORBIT_ID}/tracks",
        params=[("tags", "production"), ("tags", "ml"), ("types", "model")],
    )

    assert response.status_code == 200
    assert response.json() == {"items": [], "cursor": None}
    mock_list_tracks.assert_awaited_once_with(
        USER_ID,
        ORG_ID,
        ORBIT_ID,
        None,
        50,
        TrackSortBy.CREATED_AT,
        SortOrder.DESC,
        None,
        ["model"],
        ["production", "ml"],
    )


@patch(
    "luml.handlers.tracks.TracksHandler.list_tracks_tags",
    new_callable=AsyncMock,
)
def test_list_tracks_tags(mock_list_tags: AsyncMock) -> None:
    mock_list_tags.return_value = ["ml", "production", "staging"]
    client = create_test_client()

    response = client.get(f"/v1/organizations/{ORG_ID}/orbits/{ORBIT_ID}/tracks/tags")

    assert response.status_code == 200
    assert response.json() == ["ml", "production", "staging"]
    mock_list_tags.assert_awaited_once_with(USER_ID, ORG_ID, ORBIT_ID)
