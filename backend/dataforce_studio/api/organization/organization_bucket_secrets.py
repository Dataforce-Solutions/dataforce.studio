from fastapi import APIRouter, Request, status

from dataforce_studio.handlers.bucket_secrets import BucketSecretHandler
from dataforce_studio.infra.endpoint_responses import endpoint_responses
from dataforce_studio.schemas.bucket_secrets import (
    BucketSecret,
    BucketSecretCreateIn,
    BucketSecretUpdate,
)

bucket_secrets_router = APIRouter(
    prefix="/{organization_id}/bucket-secrets", tags=["organiztions-bucket-secrets"]
)

bucket_secret_handler = BucketSecretHandler()


@bucket_secrets_router.get(
    "", responses=endpoint_responses, response_model=list[BucketSecret]
)
async def get_organization_bucket_secrets(
    request: Request, organization_id: int
) -> list[BucketSecret]:
    return await bucket_secret_handler.get_organization_bucket_secrets(
        request.user.id, organization_id
    )


@bucket_secrets_router.post(
    "", responses=endpoint_responses, response_model=BucketSecret
)
async def create_bucket_secret(
    request: Request, organization_id: int, secret: BucketSecretCreateIn
) -> BucketSecret:
    return await bucket_secret_handler.create_bucket_secret(
        request.user.id, organization_id, secret
    )


@bucket_secrets_router.get(
    "/{secret_id}", responses=endpoint_responses, response_model=BucketSecret
)
async def get_bucket_secret(
    request: Request, organization_id: int, secret_id: int
) -> BucketSecret:
    return await bucket_secret_handler.get_bucket_secret(
        request.user.id, organization_id, secret_id
    )


@bucket_secrets_router.patch(
    "/{secret_id}", responses=endpoint_responses, response_model=BucketSecret
)
async def update_bucket_secret(
    request: Request, organization_id: int, secret_id: int, secret: BucketSecretUpdate
) -> BucketSecret:
    return await bucket_secret_handler.update_bucket_secret(
        request.user.id, organization_id, secret_id, secret
    )


@bucket_secrets_router.delete(
    "/{secret_id}", responses=endpoint_responses, status_code=status.HTTP_204_NO_CONTENT
)
async def delete_bucket_secret(
    request: Request, organization_id: int, secret_id: int
) -> None:
    await bucket_secret_handler.delete_bucket_secret(
        request.user.id, organization_id, secret_id
    )
