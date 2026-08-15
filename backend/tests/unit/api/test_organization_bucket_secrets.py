from unittest.mock import AsyncMock, patch
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient
from luml.api.organization.organization_bucket_secrets import bucket_secrets_router
from luml.models import AuthUser
from luml.schemas.bucket_secrets import (
    BucketSecretUpdate,
    BucketSecretUrls,
    BucketType,
)
from starlette.authentication import AuthCredentials, AuthenticationBackend
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.requests import HTTPConnection

USER_ID = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
ORGANIZATION_ID = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
SECRET_ID = UUID("0199c337-09f3-753e-9def-b27745e69be6")
FOREIGN_SECRET_ID = UUID("0199c337-0aa2-7b44-9d21-7e5b3c8f0a12")

URLS_PATH = f"/{ORGANIZATION_ID}/bucket-secrets/{SECRET_ID}/urls"


class _NoCredentialsBackend(AuthenticationBackend):
    async def authenticate(self, conn: HTTPConnection) -> None:
        return None


class _SignedInBackend(AuthenticationBackend):
    async def authenticate(
        self, conn: HTTPConnection
    ) -> tuple[AuthCredentials, AuthUser]:
        return AuthCredentials(["authenticated", "jwt"]), AuthUser(
            user_id=USER_ID, email="caller@example.com"
        )


def _client(backend: AuthenticationBackend) -> TestClient:
    app = FastAPI()
    app.include_router(bucket_secrets_router)
    app.add_middleware(AuthenticationMiddleware, backend=backend)
    return TestClient(app)


@patch(
    "luml.handlers.bucket_secrets.BucketSecretHandler.get_existing_bucket_urls",
    new_callable=AsyncMock,
)
def test_existing_bucket_urls_requires_authentication(
    mock_get_existing_bucket_urls: AsyncMock,
) -> None:
    response = _client(_NoCredentialsBackend()).post(
        URLS_PATH, json={"id": str(SECRET_ID), "type": "s3"}
    )

    assert response.status_code == 401
    mock_get_existing_bucket_urls.assert_not_awaited()


@patch(
    "luml.handlers.bucket_secrets.BucketSecretHandler.get_existing_bucket_urls",
    new_callable=AsyncMock,
)
def test_existing_bucket_urls_forwards_path_parameters(
    mock_get_existing_bucket_urls: AsyncMock,
) -> None:
    """The path secret id, not the body id, identifies the secret to sign for."""
    mock_get_existing_bucket_urls.return_value = BucketSecretUrls(
        presigned_url="https://bucket/put",
        download_url="https://bucket/get",
        delete_url="https://bucket/delete",
    )

    response = _client(_SignedInBackend()).post(
        URLS_PATH,
        json={"id": str(FOREIGN_SECRET_ID), "type": "s3", "bucket_name": "unsaved"},
    )

    assert response.status_code == 200
    mock_get_existing_bucket_urls.assert_awaited_once_with(
        USER_ID,
        ORGANIZATION_ID,
        SECRET_ID,
        BucketSecretUpdate(
            id=FOREIGN_SECRET_ID, type=BucketType.S3, bucket_name="unsaved"
        ),
    )
