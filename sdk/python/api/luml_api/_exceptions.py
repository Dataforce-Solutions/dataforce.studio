from collections.abc import Iterable
from typing import Literal

import httpx


def _format_resources(
    resource_type: str,
    all_values: list | None,
    has_more: bool = False,
) -> str:
    if not all_values:
        return ""

    if len(all_values) == 0:
        return f"\nYou do not have available {resource_type}s yet."

    result = f"\nAvailable {resource_type}s for configuration:"

    for item in all_values:
        result += f'\n      {resource_type}(id={item.id}, name="{item.name}")'

    if has_more:
        result += "..."

    return result


class LumlAPIError(Exception):
    """Base class for every error the LUML API SDK raises."""
    def __init__(
        self,
        message: str = "LUML Studio API error.",
    ) -> None:
        self.message = message
        super().__init__(self.message)


class CapabilityNotSupportedError(LumlAPIError):
    """A Satellite does not have the capability an operation needs.

    Raised before any request is sent: the capability is missing from the
    Satellite's `present_capabilities` on the Platform record, or the
    deployment has no monitoring URL reported."""
    capability: str
    satellite_id: str
    deployment_id: str | None

    def __init__(
        self,
        capability: str,
        satellite_id: str,
        *,
        deployment_id: str | None = None,
        message: str | None = None,
    ) -> None:
        self.capability = capability
        self.satellite_id = satellite_id
        self.deployment_id = deployment_id
        super().__init__(
            message
            or f"Satellite {satellite_id} does not support capability {capability!r}"
        )


class UnsupportedCapabilityVersionError(LumlAPIError):
    """The SDK and the Satellite share no common capability API version.

    Carries both sides: `sdk_versions` the SDK implements and
    `satellite_versions` the Satellite advertises."""
    capability: str
    satellite_id: str
    sdk_versions: tuple[int, ...]
    satellite_versions: tuple[int, ...]

    def __init__(
        self,
        capability: str,
        satellite_id: str,
        sdk_versions: Iterable[int],
        satellite_versions: Iterable[int],
    ) -> None:
        self.capability = capability
        self.satellite_id = satellite_id
        self.sdk_versions = tuple(sorted(set(sdk_versions)))
        self.satellite_versions = tuple(sorted(set(satellite_versions)))
        super().__init__(
            f"No common {capability} API version for Satellite {satellite_id}: "
            f"SDK supports {list(self.sdk_versions)}; Satellite advertises "
            f"{list(self.satellite_versions)}"
        )


class NotAvailableInVersionError(LumlAPIError):
    """The selected capability API version does not include this operation."""
    capability: str
    operation: str
    api_version: int

    def __init__(self, capability: str, operation: str, api_version: int) -> None:
        self.capability = capability
        self.operation = operation
        self.api_version = api_version
        super().__init__(
            f"{capability.capitalize()} operation {operation!r} is not available in "
            f"API version {api_version}"
        )


class ContractViolationError(LumlAPIError):
    """A Satellite response is missing the structure its declared API version requires.

    Names the Satellite and operation; `missing_fields` lists the required
    top-level fields that were absent."""
    satellite_id: str
    operation: str
    api_version: int
    response: object
    missing_fields: tuple[str, ...]

    def __init__(
        self,
        satellite_id: str,
        operation: str,
        api_version: int,
        response: object,
        missing_fields: Iterable[str],
    ) -> None:
        self.satellite_id = satellite_id
        self.operation = operation
        self.api_version = api_version
        self.response = response
        self.missing_fields = tuple(sorted(missing_fields))
        detail = (
            f"missing required top-level fields {list(self.missing_fields)}"
            if self.missing_fields
            else "response is not a JSON object"
        )
        super().__init__(
            f"Satellite {satellite_id} violated the monitoring API version "
            f"{api_version} contract for operation {operation!r}: {detail}"
        )


class ConfigurationError(LumlAPIError):
    """The client is missing configuration (organization, orbit or collection)."""
    def __init__(
        self,
        resource_type: str,
        message: str | None = None,
        all_values: list | None = None,
        has_more: bool = False,
    ) -> None:
        self.message = message if message else ""
        self.message += """
        luml = LumlClient(
            api_key="luml_api_key",
            organization=1,
            orbit=1215,
            collection=15
        )
        """
        self.message += _format_resources(resource_type, all_values, has_more)

        super().__init__(self.message)


class MultipleResourcesFoundError(LumlAPIError):
    """A name lookup matched more than one resource; use the id instead."""
    pass


class ResourceNotFoundError(Exception):
    """A resource referenced by id or name does not exist."""
    def __init__(
        self,
        resource_type: str,
        value: int | str,
        all_values: list | None = None,
        has_more: bool = False,
        message: str | None = None,
    ) -> None:
        if message:
            self.message = message
        else:
            value_reference = "id" if isinstance(value, int) else "name"
            self.message = (
                f"{resource_type} with {value_reference} '{value}'"
                f" not found. Try to set with another id or name."
            )
        self.message += _format_resources(resource_type, all_values, has_more)

        super().__init__(self.message)


class OrbitResourceNotFoundError(ResourceNotFoundError):
    """The referenced Orbit does not exist."""
    def __init__(
        self,
        value: int | str,
        all_values: list | None = None,
        has_more: bool = False,
        message: str | None = None,
    ) -> None:
        super().__init__("Orbit", value, all_values, has_more, message)


class OrganizationResourceNotFoundError(ResourceNotFoundError):
    """The referenced Organization does not exist."""
    def __init__(
        self,
        value: int | str,
        all_values: list | None = None,
        has_more: bool = False,
        message: str | None = None,
    ) -> None:
        super().__init__("Organization", value, all_values, has_more, message)


class CollectionResourceNotFoundError(ResourceNotFoundError):
    """The referenced Collection does not exist."""
    def __init__(
        self,
        value: int | str,
        all_values: list | None = None,
        has_more: bool = False,
        message: str | None = None,
    ) -> None:
        super().__init__("Collection", value, all_values, has_more, message)


class APIError(LumlAPIError):
    """Base class for errors tied to an HTTP request."""
    message: str
    request: httpx.Request
    body: object | None

    def __init__(
        self, message: str, request: httpx.Request, *, body: object | None
    ) -> None:
        super().__init__(message)
        self.request = request
        self.message = message
        self.body = body


class APIResponseValidationError(APIError):
    """The API answered, but the payload did not match the expected schema."""
    response: httpx.Response
    status_code: int

    def __init__(
        self,
        response: httpx.Response,
        body: object | None,
        *,
        message: str | None = None,
    ) -> None:
        super().__init__(
            message or "Data returned by API invalid for expected schema.",
            response.request,
            body=body,
        )
        self.response = response
        self.status_code = response.status_code


class APIStatusError(APIError):
    """Base class for non-success HTTP status responses."""
    response: httpx.Response
    status_code: int

    def __init__(
        self, message: str, *, response: httpx.Response, body: object | None
    ) -> None:
        super().__init__(message, response.request, body=body)
        self.response = response
        self.status_code = response.status_code


class BadRequestError(APIStatusError):
    """The request was malformed (HTTP 400)."""
    status_code: Literal[400] = 400


class AuthenticationError(APIStatusError):
    """The API key is missing or invalid (HTTP 401)."""
    status_code: Literal[401] = 401


class PermissionDeniedError(APIStatusError):
    """The API key lacks access to this resource (HTTP 403)."""
    status_code: Literal[403] = 403


class NotFoundError(APIStatusError):
    """The requested resource does not exist (HTTP 404)."""
    status_code: Literal[404] = 404


class SatelliteOutOfSyncError(NotFoundError):
    """A Satellite answered `unknown_route` for a path its stored capabilities promise.

    The Platform's copy of the Satellite's capabilities no longer matches the
    running build; restarting or re-pairing the Satellite refreshes it."""
    satellite_id: str
    operation: str
    api_version: int

    def __init__(
        self,
        satellite_id: str,
        operation: str,
        api_version: int,
        *,
        response: httpx.Response,
        body: object | None,
    ) -> None:
        self.satellite_id = satellite_id
        self.operation = operation
        self.api_version = api_version
        super().__init__(
            f"Satellite {satellite_id} returned unknown_route for monitoring "
            f"operation {operation!r} at API version {api_version}; restart or "
            "re-pair the Satellite so its capabilities match its routes",
            response=response,
            body=body,
        )


class ConflictError(APIStatusError):
    """The request conflicts with the resource's current state (HTTP 409)."""
    status_code: Literal[409] = 409


class UnprocessableEntityError(APIStatusError):
    """The server rejected the request's values (HTTP 422)."""
    status_code: Literal[422] = 422


class InternalServerError(APIStatusError):
    """The server failed to process the request (HTTP 5xx)."""
    pass


class FileError(Exception):
    """Base class for bucket file transfer errors."""
    pass


class FileUploadError(FileError):
    """Uploading a file to the bucket failed."""
    def __init__(self, message: str = "") -> None:
        super().__init__("Error uploading file to bucket." + message)


class FileDownloadError(FileError):
    """Downloading a file from the bucket failed."""
    def __init__(self, message: str = "") -> None:
        super().__init__("Error downloading file from bucket." + message)
