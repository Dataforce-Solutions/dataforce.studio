import datetime
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID

import pytest
from luml.handlers.bucket_secrets import BucketSecretHandler
from luml.infra.exceptions import (
    ApplicationError,
    BucketSecretInUseError,
    DatabaseConstraintError,
    InsufficientPermissionsError,
    NotFoundError,
)
from luml.schemas.bucket_secrets import (
    AzureBucketSecret,
    AzureBucketSecretCreate,
    AzureBucketSecretCreateIn,
    AzureBucketSecretOut,
    BucketSecretOut,
    BucketSecretUpdate,
    BucketSecretUpdateIn,
    BucketSecretUrls,
    BucketType,
    S3BucketSecret,
    S3BucketSecretCreateIn,
    S3BucketSecretOut,
    validate_bucket_secret_out,
)
from luml.schemas.permissions import Action, Resource
from luml.schemas.storage import (
    BucketMultipartUpload,
    PartDetails,
    S3MultiPartUploadDetails,
)

handler = BucketSecretHandler()

USER_ID = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
OTHER_ORGANIZATION_ID = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
OTHER_SECRET_ID = UUID("0199c337-0aa3-7e55-8c10-4a9f2d6b7c31")
OWNER_ORGANIZATION_ID = UUID("0199c337-0aa1-7c33-8f6c-2c6d0a4e91be")
OWNER_SECRET_ID = UUID("0199c337-0aa2-7b44-9d21-7e5b3c8f0a12")


def _owner_s3_secret() -> S3BucketSecret:
    return S3BucketSecret(
        id=OWNER_SECRET_ID,
        organization_id=OWNER_ORGANIZATION_ID,
        endpoint="owner.s3.amazonaws.com",
        bucket_name="owner-bucket",
        access_key="owner-access-key",
        secret_key="owner-secret-key",
        region="eu-west-1",
        created_at=datetime.datetime.now(),
        updated_at=None,
    )


@patch(
    "luml.handlers.bucket_secrets.BucketSecretRepository.create_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_bucket_secret(
    mock_check_permissions: AsyncMock,
    mock_create_bucket_secret: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    secret_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    secret_create_in = S3BucketSecretCreateIn(
        type=BucketType.S3,
        endpoint="s3.amazonaws.com",
        bucket_name="test-bucket",
        access_key="access_key",
        secret_key="secret_key",
        region="us-east-1",
    )
    expected = S3BucketSecretOut(
        id=secret_id,
        type=secret_create_in.type,
        organization_id=organization_id,
        endpoint=secret_create_in.endpoint,
        bucket_name=secret_create_in.bucket_name,
        region=secret_create_in.region,
        created_at=datetime.datetime.now(),
        updated_at=None,
    )

    mock_create_bucket_secret.return_value = expected

    secret = await handler.create_bucket_secret(
        user_id, organization_id, secret_create_in
    )

    assert secret == expected
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.BUCKET_SECRET, Action.CREATE
    )
    mock_create_bucket_secret.assert_awaited_once()


@patch(
    "luml.handlers.bucket_secrets.BucketSecretRepository.create_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_bucket_secret_azure(
    mock_check_permissions: AsyncMock,
    mock_create_bucket_secret: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    secret_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    secret_create_in = AzureBucketSecretCreateIn(
        type=BucketType.AZURE,
        endpoint="DefaultEndpointsProtocol=https;AccountName=testbucket;AccountKey=+l0j8/86NqqQbn8oZReRUDCEkmGLBJS+AStrrQv9Q==;EndpointSuffix=core.windows.net",
        bucket_name="test-bucket",
    )
    expected = AzureBucketSecretOut(
        id=secret_id,
        type=secret_create_in.type,
        organization_id=organization_id,
        endpoint=secret_create_in.endpoint,
        bucket_name=secret_create_in.bucket_name,
        created_at=datetime.datetime.now(),
        updated_at=None,
    )

    mock_create_bucket_secret.return_value = expected

    secret = await handler.create_bucket_secret(
        user_id, organization_id, secret_create_in
    )

    assert secret == expected
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.BUCKET_SECRET, Action.CREATE
    )
    mock_create_bucket_secret.assert_awaited_once()


@patch(
    "luml.handlers.bucket_secrets.BucketSecretRepository.create_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_bucket_secret_s3_not_unique(
    mock_check_permissions: AsyncMock,
    mock_create_bucket_secret: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")

    secret_create_in = AzureBucketSecretCreateIn(
        type=BucketType.AZURE,
        endpoint="DefaultEndpointsProtocol=https;AccountName=testbucket;AccountKey=+l0j8/86NqqQbn8oZReRUDCEkmGLBJS+AStrrQv9Q==;EndpointSuffix=core.windows.net",
        bucket_name="test-bucket",
    )

    secret_create = AzureBucketSecretCreate(
        type=secret_create_in.type,
        organization_id=organization_id,
        endpoint=secret_create_in.endpoint,
        bucket_name=secret_create_in.bucket_name,
    )

    mock_create_bucket_secret.side_effect = DatabaseConstraintError(status_code=409)

    with pytest.raises(
        ApplicationError,
        match="Bucket secret with the given bucket name and endpoint already exists.",
    ) as error:
        await handler.create_bucket_secret(user_id, organization_id, secret_create_in)

    assert error.value.status_code == 409
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.BUCKET_SECRET, Action.CREATE
    )
    mock_create_bucket_secret.assert_awaited_once_with(secret_create)


@patch(
    "luml.handlers.bucket_secrets.BucketSecretRepository.get_organization_bucket_secrets",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_organization_bucket_secrets(
    mock_check_permissions: AsyncMock,
    mock_get_organization_bucket_secrets: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    secret_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    expected = [
        S3BucketSecretOut(
            id=secret_id,
            organization_id=organization_id,
            endpoint="s3.amazonaws.com",
            bucket_name="test-bucket-1",
            region="us-east-1",
            type=BucketType.S3,
            created_at=datetime.datetime.now(),
            updated_at=None,
        )
    ]

    mock_get_organization_bucket_secrets.return_value = expected

    secrets = await handler.get_organization_bucket_secrets(user_id, organization_id)

    assert secrets == expected
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.BUCKET_SECRET, Action.LIST
    )
    mock_get_organization_bucket_secrets.assert_awaited_once_with(organization_id)


@patch(
    "luml.handlers.bucket_secrets.BucketSecretRepository.get_bucket_secret_details",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_bucket_secret(
    mock_check_permissions: AsyncMock,
    mock_get_bucket_secret_details: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    secret_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    expected = S3BucketSecretOut(
        id=secret_id,
        organization_id=organization_id,
        endpoint="s3.amazonaws.com",
        bucket_name="test-bucket",
        region="us-east-1",
        type=BucketType.S3,
        created_at=datetime.datetime.now(),
        updated_at=None,
    )

    mock_get_bucket_secret_details.return_value = expected

    secret = await handler.get_bucket_secret(user_id, organization_id, secret_id)

    assert secret == expected
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.BUCKET_SECRET, Action.READ
    )
    mock_get_bucket_secret_details.assert_awaited_once_with(secret_id, organization_id)


@patch(
    "luml.handlers.bucket_secrets.BucketSecretRepository.get_bucket_secret_details",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_bucket_secret_not_found(
    mock_check_permissions: AsyncMock,
    mock_get_bucket_secret_details: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    secret_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    mock_get_bucket_secret_details.return_value = None

    with pytest.raises(NotFoundError, match="Secret not found") as error:
        await handler.get_bucket_secret(user_id, organization_id, secret_id)

    assert error.value.status_code == 404
    mock_get_bucket_secret_details.assert_awaited_once_with(secret_id, organization_id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.BUCKET_SECRET, Action.READ
    )


@patch(
    "luml.handlers.bucket_secrets.BucketSecretRepository.update_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.bucket_secrets.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_bucket_secret(
    mock_check_permissions: AsyncMock,
    mock_get_bucket_secret: AsyncMock,
    mock_update_bucket_secret: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    secret_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    secret_update = BucketSecretUpdate(
        id=secret_id,
        endpoint="s3.amazonaws.com",
        bucket_name="updated-bucket",
    )
    existing = S3BucketSecret(
        id=secret_id,
        organization_id=organization_id,
        region="us-east-1",
        endpoint="original-endpoint",
        bucket_name="original-bucket",
        created_at=datetime.datetime.now(),
        updated_at=None,
    )
    expected = S3BucketSecretOut(
        id=secret_id,
        organization_id=organization_id,
        region="us-east-1",
        type=BucketType.S3,
        endpoint=secret_update.endpoint or "default-endpoint",
        bucket_name=secret_update.bucket_name or "default-bucket",
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
    )

    mock_get_bucket_secret.return_value = existing
    mock_update_bucket_secret.return_value = expected

    secret = await handler.update_bucket_secret(
        user_id, organization_id, secret_id, secret_update
    )

    assert secret == expected
    mock_get_bucket_secret.assert_awaited_once_with(secret_id, organization_id)
    mock_update_bucket_secret.assert_awaited_once()
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.BUCKET_SECRET, Action.UPDATE
    )


@patch(
    "luml.handlers.bucket_secrets.BucketSecretRepository.update_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.bucket_secrets.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_bucket_secret_s3_not_unique(
    mock_check_permissions: AsyncMock,
    mock_get_bucket_secret: AsyncMock,
    mock_update_bucket_secret: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    secret_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    secret_update = BucketSecretUpdate(
        id=secret_id,
        endpoint="DefaultEndpointsProtocol=https;AccountName=testbucket;AccountKey=+l0j8/86NqqQbn8oZReRUDCEkmGLBJS+AStrrQv9Q==;EndpointSuffix=core.windows.net",
        bucket_name="test-bucket",
    )
    existing = AzureBucketSecret(
        id=secret_id,
        organization_id=organization_id,
        endpoint="original-endpoint",
        bucket_name="original-bucket",
        created_at=datetime.datetime.now(),
        updated_at=None,
    )

    mock_get_bucket_secret.return_value = existing
    mock_update_bucket_secret.side_effect = DatabaseConstraintError(status_code=409)

    with pytest.raises(
        ApplicationError,
        match="Bucket secret with the given bucket name and endpoint already exists.",
    ) as error:
        await handler.update_bucket_secret(
            user_id, organization_id, secret_id, secret_update
        )

    assert error.value.status_code == 409
    mock_get_bucket_secret.assert_awaited_once_with(secret_id, organization_id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.BUCKET_SECRET, Action.UPDATE
    )
    mock_update_bucket_secret.assert_awaited_once()


@patch(
    "luml.handlers.bucket_secrets.BucketSecretRepository.update_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.bucket_secrets.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_bucket_secret_not_found(
    mock_check_permissions: AsyncMock,
    mock_get_bucket_secret: AsyncMock,
    mock_update_bucket_secret: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    secret_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    secret_update = BucketSecretUpdate(
        id=secret_id,
        endpoint="s3.amazonaws.com",
        bucket_name="updated-bucket",
    )

    mock_get_bucket_secret.return_value = None

    with pytest.raises(NotFoundError, match="Secret not found") as error:
        await handler.update_bucket_secret(
            user_id, organization_id, secret_id, secret_update
        )

    assert error.value.status_code == 404
    mock_get_bucket_secret.assert_awaited_once_with(secret_id, organization_id)
    mock_update_bucket_secret.assert_not_called()
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.BUCKET_SECRET, Action.UPDATE
    )


@patch(
    "luml.handlers.bucket_secrets.BucketSecretRepository.update_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.bucket_secrets.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_bucket_secret_azure_forbidden_fields(
    mock_check_permissions: AsyncMock,
    mock_get_bucket_secret: AsyncMock,
    mock_update_bucket_secret: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    secret_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    secret_update = BucketSecretUpdate(
        id=secret_id,
        endpoint="blob.core.windows.net",
        bucket_name="test-bucket",
        access_key="should-not-be-here",
    )
    existing = AzureBucketSecret(
        id=secret_id,
        organization_id=organization_id,
        endpoint="original-endpoint",
        bucket_name="original-bucket",
        created_at=datetime.datetime.now(),
        updated_at=None,
    )

    mock_get_bucket_secret.return_value = existing

    with pytest.raises(ApplicationError) as error:
        await handler.update_bucket_secret(
            user_id, organization_id, secret_id, secret_update
        )

    assert error.value.status_code == 400
    mock_get_bucket_secret.assert_awaited_once_with(secret_id, organization_id)
    mock_update_bucket_secret.assert_not_called()


@patch(
    "luml.handlers.bucket_secrets.BucketSecretRepository.update_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.bucket_secrets.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_bucket_secret_toctou_not_found(
    mock_check_permissions: AsyncMock,
    mock_get_bucket_secret: AsyncMock,
    mock_update_bucket_secret: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    secret_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    secret_update = BucketSecretUpdate(
        id=secret_id,
        endpoint="s3.amazonaws.com",
        bucket_name="updated-bucket",
    )
    existing = S3BucketSecret(
        id=secret_id,
        organization_id=organization_id,
        region="us-east-1",
        endpoint="original-endpoint",
        bucket_name="original-bucket",
        created_at=datetime.datetime.now(),
        updated_at=None,
    )

    mock_get_bucket_secret.return_value = existing
    mock_update_bucket_secret.return_value = None

    with pytest.raises(NotFoundError, match="Secret not found") as error:
        await handler.update_bucket_secret(
            user_id, organization_id, secret_id, secret_update
        )

    assert error.value.status_code == 404
    mock_get_bucket_secret.assert_awaited_once_with(secret_id, organization_id)
    mock_update_bucket_secret.assert_awaited_once()


@patch(
    "luml.handlers.bucket_secrets.BucketSecretRepository.delete_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_bucket_secret(
    mock_check_permissions: AsyncMock,
    mock_delete_bucket_secret: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    secret_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    mock_delete_bucket_secret.return_value = True

    await handler.delete_bucket_secret(user_id, organization_id, secret_id)

    mock_delete_bucket_secret.assert_awaited_once_with(secret_id, organization_id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.BUCKET_SECRET, Action.DELETE
    )


@patch(
    "luml.handlers.bucket_secrets.BucketSecretRepository.delete_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_bucket_secret_in_use(
    mock_check_permissions: AsyncMock,
    mock_delete_bucket_secret: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    secret_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    mock_delete_bucket_secret.side_effect = DatabaseConstraintError()

    with pytest.raises(BucketSecretInUseError) as error:
        await handler.delete_bucket_secret(user_id, organization_id, secret_id)

    assert error.value.status_code == 409
    mock_delete_bucket_secret.assert_awaited_once_with(secret_id, organization_id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.BUCKET_SECRET, Action.DELETE
    )


@patch("luml.handlers.bucket_secrets.create_storage_client")
@pytest.mark.asyncio
async def test_generate_bucket_urls(
    mock_create_storage_client: Mock,
) -> None:
    secret = S3BucketSecretCreateIn(
        endpoint="s3.amazonaws.com",
        bucket_name="test-bucket",
        access_key="access_key",
        secret_key="secret_key",
        region="us-east-1",
    )
    object_name = "test_file"

    presigned_url = "https://test-bucket.s3.amazonaws.com/test_file?presigned=true"
    download_url = "https://test-bucket.s3.amazonaws.com/test_file?download=true"
    delete_url = "https://test-bucket.s3.amazonaws.com/test_file?delete=true"

    expected = BucketSecretUrls(
        presigned_url=presigned_url,
        download_url=download_url,
        delete_url=delete_url,
    )

    mock_storage_instance = Mock()
    mock_storage_instance.get_upload_url = AsyncMock(return_value=presigned_url)
    mock_storage_instance.get_download_url = AsyncMock(return_value=download_url)
    mock_storage_instance.get_delete_url = AsyncMock(return_value=delete_url)

    mock_service_class = Mock(return_value=mock_storage_instance)
    mock_create_storage_client.return_value = mock_service_class

    urls = await handler.generate_bucket_urls(secret)

    assert urls == expected
    mock_create_storage_client.assert_called_once_with(secret.type)
    mock_service_class.assert_called_once_with(secret)
    mock_storage_instance.get_upload_url.assert_awaited_once_with(object_name)
    mock_storage_instance.get_download_url.assert_awaited_once_with(object_name)
    mock_storage_instance.get_delete_url.assert_awaited_once_with(object_name)


@patch("luml.handlers.bucket_secrets.create_storage_client")
@patch(
    "luml.handlers.bucket_secrets.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_existing_bucket_urls(
    mock_check_permissions: AsyncMock,
    mock_get_bucket_secret: AsyncMock,
    mock_create_storage_client: Mock,
) -> None:
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    secret_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    original_secret = S3BucketSecret(
        id=secret_id,
        organization_id=organization_id,
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
        endpoint="s3.amazonaws.com",
        bucket_name="original_name",
        access_key="access_key",
        secret_key="secret_key",
        session_token=None,
        secure=True,
        region="us-east-1",
        cert_check=None,
    )
    secret = BucketSecretUpdate(
        id=secret_id,
        endpoint="new.s3.amazonaws.com",
        bucket_name="new-bucket-name",
        access_key="new-access_key",
    )

    object_name = "test_file"

    presigned_url = "https://test-bucket.s3.amazonaws.com/test_file?presigned=true"
    download_url = "https://test-bucket.s3.amazonaws.com/test_file?download=true"
    delete_url = "https://test-bucket.s3.amazonaws.com/test_file?delete=true"

    expected = BucketSecretUrls(
        presigned_url=presigned_url,
        download_url=download_url,
        delete_url=delete_url,
    )

    mock_storage_instance = Mock()
    mock_storage_instance.get_upload_url = AsyncMock(return_value=presigned_url)
    mock_storage_instance.get_download_url = AsyncMock(return_value=download_url)
    mock_storage_instance.get_delete_url = AsyncMock(return_value=delete_url)

    mock_service_class = Mock(return_value=mock_storage_instance)
    mock_create_storage_client.return_value = mock_service_class
    mock_get_bucket_secret.return_value = original_secret

    urls = await handler.get_existing_bucket_urls(
        USER_ID, organization_id, secret_id, secret
    )

    assert urls == expected
    mock_check_permissions.assert_awaited_once_with(
        organization_id, USER_ID, Resource.BUCKET_SECRET, Action.READ
    )
    mock_get_bucket_secret.assert_awaited_once_with(secret_id, organization_id)
    mock_create_storage_client.assert_called_once()
    mock_storage_instance.get_upload_url.assert_awaited_once_with(object_name)
    mock_storage_instance.get_download_url.assert_awaited_once_with(object_name)
    mock_storage_instance.get_delete_url.assert_awaited_once_with(object_name)

    (signed_secret,) = mock_service_class.call_args.args
    assert signed_secret.endpoint == "new.s3.amazonaws.com"
    assert signed_secret.bucket_name == "new-bucket-name"
    assert signed_secret.access_key == "new-access_key"
    assert signed_secret.secret_key == original_secret.secret_key


@patch("luml.handlers.bucket_secrets.create_storage_client")
@patch(
    "luml.handlers.bucket_secrets.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_existing_bucket_urls_type_cant_be_changed(
    mock_check_permissions: AsyncMock,
    mock_get_bucket_secret: AsyncMock,
    mock_create_storage_client: Mock,
) -> None:
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    secret_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    original_secret = Mock(id=secret_id, type=BucketType.S3)

    secret = BucketSecretUpdate(
        id=secret_id,
        bucket_name="new-bucket-name",
        type=BucketType.AZURE,
    )

    mock_get_bucket_secret.return_value = original_secret

    with pytest.raises(ApplicationError) as error:
        await handler.get_existing_bucket_urls(
            USER_ID, organization_id, secret_id, secret
        )

    assert error.value.status_code == 400
    mock_get_bucket_secret.assert_awaited_once_with(secret_id, organization_id)
    mock_create_storage_client.assert_not_called()


@patch(
    "luml.handlers.bucket_secrets.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_existing_bucket_urls_secret_not_found(
    mock_check_permissions: AsyncMock,
    mock_get_bucket_secret: AsyncMock,
) -> None:
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    secret_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    secret = BucketSecretUpdate(
        id=secret_id,
        bucket_name="new-bucket-name",
        access_key="new-access_key",
    )

    mock_get_bucket_secret.return_value = None

    with pytest.raises(NotFoundError) as error:
        await handler.get_existing_bucket_urls(
            USER_ID, organization_id, secret_id, secret
        )

    assert error.value.status_code == 404


@patch("luml.handlers.bucket_secrets.create_storage_client")
@pytest.mark.asyncio
async def test_get_bucket_urls(
    mock_create_storage_client: Mock,
) -> None:
    secret = S3BucketSecretCreateIn(
        endpoint="s3.amazonaws.com",
        bucket_name="test-bucket",
        access_key="access_key",
        secret_key="secret_key",
        region="us-east-1",
    )
    object_name = "test_file"

    presigned_url = "https://test-bucket.s3.amazonaws.com/test_file?presigned=true"
    download_url = "https://test-bucket.s3.amazonaws.com/test_file?download=true"
    delete_url = "https://test-bucket.s3.amazonaws.com/test_file?delete=true"

    expected = BucketSecretUrls(
        presigned_url=presigned_url,
        download_url=download_url,
        delete_url=delete_url,
    )

    mock_storage_instance = AsyncMock()
    mock_storage_instance.bucket_exists.return_value = True
    mock_storage_instance.get_upload_url.return_value = presigned_url
    mock_storage_instance.get_download_url.return_value = download_url
    mock_storage_instance.get_delete_url.return_value = delete_url

    mock_service_class = Mock(return_value=mock_storage_instance)
    mock_create_storage_client.return_value = mock_service_class

    urls = await handler.get_bucket_urls(secret)

    assert urls == expected
    mock_create_storage_client.assert_called_once_with(secret.type)
    mock_service_class.assert_called_once_with(secret)
    mock_storage_instance.get_upload_url.assert_awaited_once_with(object_name)
    mock_storage_instance.get_download_url.assert_awaited_once_with(object_name)
    mock_storage_instance.get_delete_url.assert_awaited_once_with(object_name)


@patch("luml.handlers.bucket_secrets.create_storage_client")
@patch(
    "luml.handlers.bucket_secrets.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_bucket_multipart_urls(
    mock_check_permissions: AsyncMock,
    mock_get_bucket_secret: AsyncMock,
    mock_create_storage_client: Mock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    secret_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    bucket_location = "orbit/collection/model.tar.gz"
    file_size = 10485760
    upload_id = "upload_id"

    original_secret = S3BucketSecret(
        id=secret_id,
        organization_id=organization_id,
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
        endpoint="s3.amazonaws.com",
        bucket_name="test-bucket",
        access_key="access_key",
        secret_key="secret_key",
        session_token=None,
        secure=True,
        region="us-east-1",
        cert_check=None,
    )

    data = BucketMultipartUpload(
        bucket_id=secret_id,
        bucket_location=bucket_location,
        size=file_size,
        upload_id=upload_id,
    )

    expected = S3MultiPartUploadDetails(
        upload_id=upload_id,
        parts=[
            PartDetails(
                part_number=1,
                url="https://test-bucket.s3.amazonaws.com/orbit/collection/model.tar.gz?partNumber=1",
                start_byte=0,
                end_byte=5242879,
                part_size=5242880,
            ),
            PartDetails(
                part_number=2,
                url="https://test-bucket.s3.amazonaws.com/orbit/collection/model.tar.gz?partNumber=2",
                start_byte=5242880,
                end_byte=10485759,
                part_size=5242880,
            ),
        ],
        complete_url="https://test-bucket.s3.amazonaws.com/orbit/collection/model.tar.gz?complete",
    )

    mock_storage_instance = Mock()
    mock_storage_instance.create_multipart_upload = AsyncMock(return_value=expected)

    mock_service_class = Mock(return_value=mock_storage_instance)
    mock_create_storage_client.return_value = mock_service_class
    mock_get_bucket_secret.return_value = original_secret

    result = await handler.get_bucket_multipart_urls(user_id, data)

    assert result == expected
    mock_get_bucket_secret.assert_awaited_once_with(secret_id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.BUCKET_SECRET, Action.READ
    )
    mock_create_storage_client.assert_called_once_with(original_secret.type)
    mock_service_class.assert_called_once_with(original_secret)
    mock_storage_instance.create_multipart_upload.assert_awaited_once_with(
        bucket_location, file_size, upload_id
    )


@patch("luml.handlers.bucket_secrets.create_storage_client")
@patch(
    "luml.handlers.bucket_secrets.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_bucket_multipart_urls_not_found(
    mock_get_bucket_secret: AsyncMock,
    mock_create_storage_client: Mock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    secret_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    data = BucketMultipartUpload(
        bucket_id=secret_id,
        bucket_location="orbit/collection/model.tar.gz",
        size=10485760,
        upload_id="upload_id",
    )

    mock_get_bucket_secret.return_value = None

    with pytest.raises(NotFoundError) as error:
        await handler.get_bucket_multipart_urls(user_id, data)

    assert error.value.status_code == 404
    mock_get_bucket_secret.assert_awaited_once_with(secret_id)
    mock_create_storage_client.assert_not_called()


@patch(
    "luml.handlers.bucket_secrets.BucketSecretRepository.get_bucket_secret_details",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_bucket_secret_from_another_organization(
    mock_check_permissions: AsyncMock,
    mock_get_bucket_secret_details: AsyncMock,
) -> None:
    stored = _owner_s3_secret()

    async def scoped_details(
        secret_id: UUID, organization_id: UUID
    ) -> BucketSecretOut | None:
        if secret_id != stored.id or organization_id != stored.organization_id:
            return None
        return validate_bucket_secret_out(stored)

    mock_get_bucket_secret_details.side_effect = scoped_details

    with pytest.raises(NotFoundError) as error:
        await handler.get_bucket_secret(USER_ID, OTHER_ORGANIZATION_ID, OWNER_SECRET_ID)

    assert error.value.status_code == 404
    assert str(error.value) == "Secret not found"
    mock_check_permissions.assert_awaited_once_with(
        OTHER_ORGANIZATION_ID, USER_ID, Resource.BUCKET_SECRET, Action.READ
    )


@patch(
    "luml.handlers.bucket_secrets.BucketSecretRepository.update_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.bucket_secrets.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_bucket_secret_from_another_organization(
    mock_check_permissions: AsyncMock,
    mock_get_bucket_secret: AsyncMock,
    mock_update_bucket_secret: AsyncMock,
) -> None:
    stored = {OWNER_SECRET_ID: _owner_s3_secret()}

    async def scoped_get(
        secret_id: UUID, organization_id: UUID | None = None
    ) -> S3BucketSecret | None:
        secret = stored.get(secret_id)
        if not secret:
            return None
        if organization_id is not None and secret.organization_id != organization_id:
            return None
        return secret

    async def scoped_update(
        secret: BucketSecretUpdate, organization_id: UUID
    ) -> S3BucketSecret | None:
        if not await scoped_get(secret.id, organization_id):
            return None
        stored[secret.id] = stored[secret.id].model_copy(
            update=secret.model_dump(exclude_unset=True, exclude={"id"})
        )
        return stored[secret.id]

    mock_get_bucket_secret.side_effect = scoped_get
    mock_update_bucket_secret.side_effect = scoped_update

    with pytest.raises(NotFoundError) as error:
        await handler.update_bucket_secret(
            USER_ID,
            OTHER_ORGANIZATION_ID,
            OWNER_SECRET_ID,
            BucketSecretUpdateIn(
                endpoint="other.s3.amazonaws.com",
                bucket_name="other-bucket",
                access_key="other-access-key",
                secret_key="other-secret-key",
                region="other-region",
            ),
        )

    assert error.value.status_code == 404
    assert str(error.value) == "Secret not found"
    mock_update_bucket_secret.assert_not_called()

    owner_secret = stored[OWNER_SECRET_ID]
    assert owner_secret.endpoint == "owner.s3.amazonaws.com"
    assert owner_secret.bucket_name == "owner-bucket"
    assert owner_secret.access_key == "owner-access-key"
    assert owner_secret.secret_key == "owner-secret-key"
    assert owner_secret.region == "eu-west-1"


@patch(
    "luml.handlers.bucket_secrets.BucketSecretRepository.update_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.bucket_secrets.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_bucket_secret_from_another_organization_hides_bucket_type(
    mock_check_permissions: AsyncMock,
    mock_get_bucket_secret: AsyncMock,
    mock_update_bucket_secret: AsyncMock,
) -> None:
    """The Azure-forbidden-fields check must not become a type oracle."""
    stored = AzureBucketSecret(
        id=OWNER_SECRET_ID,
        organization_id=OWNER_ORGANIZATION_ID,
        endpoint="owner.blob.core.windows.net",
        bucket_name="owner-bucket",
        created_at=datetime.datetime.now(),
        updated_at=None,
    )

    async def scoped_get(
        secret_id: UUID, organization_id: UUID | None = None
    ) -> AzureBucketSecret | None:
        if secret_id != stored.id:
            return None
        if organization_id is not None and stored.organization_id != organization_id:
            return None
        return stored

    mock_get_bucket_secret.side_effect = scoped_get

    with pytest.raises(NotFoundError) as error:
        await handler.update_bucket_secret(
            USER_ID,
            OTHER_ORGANIZATION_ID,
            OWNER_SECRET_ID,
            BucketSecretUpdateIn(access_key="probe"),
        )

    assert error.value.status_code == 404
    mock_update_bucket_secret.assert_not_called()


@patch(
    "luml.handlers.bucket_secrets.BucketSecretRepository.delete_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_bucket_secret_from_another_organization(
    mock_check_permissions: AsyncMock,
    mock_delete_bucket_secret: AsyncMock,
) -> None:
    stored = {OWNER_SECRET_ID: _owner_s3_secret()}

    async def scoped_delete(secret_id: UUID, organization_id: UUID) -> bool:
        secret = stored.get(secret_id)
        if not secret or secret.organization_id != organization_id:
            return False
        del stored[secret_id]
        return True

    mock_delete_bucket_secret.side_effect = scoped_delete

    with pytest.raises(NotFoundError) as error:
        await handler.delete_bucket_secret(
            USER_ID, OTHER_ORGANIZATION_ID, OWNER_SECRET_ID
        )

    assert error.value.status_code == 404
    assert str(error.value) == "Secret not found"
    assert OWNER_SECRET_ID in stored


@patch(
    "luml.handlers.bucket_secrets.BucketSecretRepository.delete_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_bucket_secret_not_found(
    mock_check_permissions: AsyncMock,
    mock_delete_bucket_secret: AsyncMock,
) -> None:
    """A missing secret must fail exactly like a foreign one: 404, same message."""
    mock_delete_bucket_secret.return_value = False

    with pytest.raises(NotFoundError) as error:
        await handler.delete_bucket_secret(
            USER_ID, OTHER_ORGANIZATION_ID, OWNER_SECRET_ID
        )

    assert error.value.status_code == 404
    assert str(error.value) == "Secret not found"


async def _scoped_get_bucket_secret(
    secret_id: UUID, organization_id: UUID | None = None
) -> S3BucketSecret | None:
    stored = {
        OWNER_SECRET_ID: _owner_s3_secret(),
        OTHER_SECRET_ID: _owner_s3_secret().model_copy(
            update={
                "id": OTHER_SECRET_ID,
                "organization_id": OTHER_ORGANIZATION_ID,
            }
        ),
    }
    secret = stored.get(secret_id)
    if not secret:
        return None
    if organization_id is not None and secret.organization_id != organization_id:
        return None
    return secret


@patch("luml.handlers.bucket_secrets.create_storage_client")
@patch(
    "luml.handlers.bucket_secrets.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_existing_bucket_urls_requires_permission(
    mock_check_permissions: AsyncMock,
    mock_get_bucket_secret: AsyncMock,
    mock_create_storage_client: Mock,
) -> None:
    mock_check_permissions.side_effect = InsufficientPermissionsError()
    mock_get_bucket_secret.side_effect = _scoped_get_bucket_secret

    with pytest.raises(InsufficientPermissionsError) as error:
        await handler.get_existing_bucket_urls(
            USER_ID,
            OWNER_ORGANIZATION_ID,
            OWNER_SECRET_ID,
            BucketSecretUpdate(id=OWNER_SECRET_ID),
        )

    assert error.value.status_code == 403
    mock_get_bucket_secret.assert_not_called()
    mock_create_storage_client.assert_not_called()


@patch("luml.handlers.bucket_secrets.create_storage_client")
@patch(
    "luml.handlers.bucket_secrets.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_existing_bucket_urls_from_another_organization(
    mock_check_permissions: AsyncMock,
    mock_get_bucket_secret: AsyncMock,
    mock_create_storage_client: Mock,
) -> None:
    mock_get_bucket_secret.side_effect = _scoped_get_bucket_secret

    with pytest.raises(NotFoundError) as error:
        await handler.get_existing_bucket_urls(
            USER_ID,
            OTHER_ORGANIZATION_ID,
            OWNER_SECRET_ID,
            BucketSecretUpdate(id=OWNER_SECRET_ID),
        )

    assert error.value.status_code == 404
    assert str(error.value) == "Secret not found"
    mock_check_permissions.assert_awaited_once_with(
        OTHER_ORGANIZATION_ID, USER_ID, Resource.BUCKET_SECRET, Action.READ
    )
    mock_create_storage_client.assert_not_called()


@patch("luml.handlers.bucket_secrets.create_storage_client")
@patch(
    "luml.handlers.bucket_secrets.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_existing_bucket_urls_body_id_must_match_path(
    mock_check_permissions: AsyncMock,
    mock_get_bucket_secret: AsyncMock,
    mock_create_storage_client: Mock,
) -> None:
    """The body id is never used to load a secret, even for a legitimate path id."""
    mock_get_bucket_secret.side_effect = _scoped_get_bucket_secret

    with pytest.raises(ApplicationError) as error:
        await handler.get_existing_bucket_urls(
            USER_ID,
            OTHER_ORGANIZATION_ID,
            OTHER_SECRET_ID,
            BucketSecretUpdate(id=OWNER_SECRET_ID),
        )

    assert error.value.status_code == 400
    mock_get_bucket_secret.assert_not_called()
    mock_create_storage_client.assert_not_called()
