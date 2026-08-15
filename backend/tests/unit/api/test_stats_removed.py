from unittest.mock import AsyncMock, patch
from uuid import UUID

from fastapi.testclient import TestClient
from luml.models import AuthUser
from luml.service import AppService
from starlette.authentication import AuthCredentials

USER_ID = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")

STATS_EMAIL_SEND_PATH = "/v1/stats/email-send"
WAITLIST_PAYLOAD = {"email": "waitlist@example.com", "description": "landing"}


def test_stats_email_send_is_not_routed_for_an_anonymous_caller() -> None:
    response = TestClient(AppService()).post(
        STATS_EMAIL_SEND_PATH, json=WAITLIST_PAYLOAD
    )

    assert response.status_code == 404


@patch(
    "luml.infra.security.JWTAuthenticationBackend.authenticate",
    new_callable=AsyncMock,
)
def test_stats_email_send_is_not_routed_for_an_authenticated_caller(
    mock_authenticate: AsyncMock,
) -> None:
    mock_authenticate.return_value = (
        AuthCredentials(["authenticated", "jwt"]),
        AuthUser(user_id=USER_ID, email="caller@example.com"),
    )

    response = TestClient(AppService()).post(
        STATS_EMAIL_SEND_PATH, json=WAITLIST_PAYLOAD
    )

    assert response.status_code == 404


def test_stats_email_send_is_absent_from_the_openapi_schema() -> None:
    assert STATS_EMAIL_SEND_PATH not in AppService().openapi()["paths"]
