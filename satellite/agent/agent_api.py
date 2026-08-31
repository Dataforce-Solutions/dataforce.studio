import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exception_handlers import http_exception_handler
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.exceptions import HTTPException as StarletteHTTPException

from agent._exceptions import DeploymentNotHostedError
from agent.clients import ModelServerError
from agent.handlers.handler_instances import ms_handler
from agent.handlers.openapi_handler import OpenAPIHandler
from agent.monitoring import IntrospectFn, register_monitoring
from agent.monitoring.api import MONITORING_FACET, build_machine_router
from agent.monitoring.app import MONITORING_APP_PATH
from agent.monitoring.greptime_query import GreptimeQueryStore
from agent.monitoring.health import HealthSnapshot, worker_health
from agent.schemas import (
    DeploymentInfo,
    Healthz,
    InferenceAccessIn,
    InferenceAccessOut,
)
from agent.schemas.deployments import detect_model_kind
from agent.schemas.monitoring_query import ProfileStatus
from agent.settings import config

openapi_handler = OpenAPIHandler(ms_handler)

# TODO fix frontend env

SATELLITE_FACET = "satellite"
DEPLOYMENT_FACET = "deployment"
INFERENCE_ACCESS_PATH = "/satellites/deployments/inference-access"
_HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete", "options", "head", "trace"})


class OpenAPISchemaBuilder:
    @staticmethod
    def generate_base_schema(app: FastAPI) -> dict[str, Any]:
        return get_openapi(
            title="Satellite Agent API",
            version="1.0.0",
            description="API for managing model deployments and inference",
            routes=app.routes,
            tags=[
                {
                    "name": SATELLITE_FACET,
                    "description": "Operations about the Satellite itself.",
                },
                {
                    "name": DEPLOYMENT_FACET,
                    "description": "Operations for deployments hosted by the Satellite.",
                },
                {
                    "name": MONITORING_FACET,
                    "description": "Monitoring operations for one hosted deployment.",
                },
            ],
        )

    @staticmethod
    def add_security_to_schema(openapi_schema: dict[str, Any]) -> None:
        for path, path_data in openapi_schema.get("paths", {}).items():
            for method_data in path_data.values():
                if not isinstance(method_data, dict) or not method_data.get("tags"):
                    continue
                method_data["security"] = (
                    [] if path == INFERENCE_ACCESS_PATH else [{"HTTPBearer": []}]
                )

        components = openapi_schema.setdefault("components", {})
        security_schemes = components.setdefault("securitySchemes", {})
        security_schemes["HTTPBearer"] = {"type": "http", "scheme": "bearer"}

    @classmethod
    def generate_full_static_schema(cls, app: FastAPI) -> dict[str, Any]:
        openapi_schema = cls.generate_base_schema(app)
        cls.add_security_to_schema(openapi_schema)
        return openapi_schema

    @classmethod
    def generate_static_schema(cls, app: FastAPI, facets: set[str]) -> dict[str, Any]:
        openapi_schema = cls.generate_full_static_schema(app)

        paths = openapi_schema.get("paths", {})
        filtered_paths: dict[str, Any] = {}
        if isinstance(paths, dict):
            for path, path_data in paths.items():
                if not isinstance(path_data, dict):
                    continue
                operations = {
                    method: operation
                    for method, operation in path_data.items()
                    if method in _HTTP_METHODS
                    and isinstance(operation, dict)
                    and isinstance(operation.get("tags"), list)
                    and len(operation["tags"]) == 1
                    and operation["tags"][0] in facets
                }
                if operations:
                    filtered_paths[path] = {
                        **{
                            key: value
                            for key, value in path_data.items()
                            if key not in _HTTP_METHODS
                        },
                        **operations,
                    }
        openapi_schema["paths"] = filtered_paths

        tag_definitions = openapi_schema.get("tags")
        if isinstance(tag_definitions, list):
            openapi_schema["tags"] = [
                tag
                for tag in tag_definitions
                if isinstance(tag, dict) and tag.get("name") in facets
            ]
        return openapi_schema


def _deployment_reference_profile(deployment_id: UUID) -> dict[str, Any] | None:
    """The artifact's reference profile for a deployment, as loaded on the deploy path."""
    deployment = ms_handler.deployments.get(str(deployment_id))
    return deployment.reference_profile if deployment else None


def _deployment_profile_status(deployment_id: UUID) -> ProfileStatus:
    deployment = ms_handler.deployments.get(str(deployment_id))
    return deployment.profile_status if deployment else ProfileStatus.ABSENT


def _worker_health(deployment_id: UUID) -> tuple[HealthSnapshot, tuple[float, float]]:
    """The worker's counters for one deployment, plus the cadence it runs at."""
    return (
        worker_health.snapshot(str(deployment_id)),
        (config.MONITORING_WINDOW_SEC, config.MONITORING_INTERVAL_SEC),
    )


def _deployment_descriptor(deployment_id: UUID) -> dict[str, Any] | None:
    """Identity of a deployment for the dashboard header.

    Everything but the task type comes from the Platform record the Agent syncs; the task
    type is a property of the trained model, so it comes from the artifact's profile.
    """
    deployment = ms_handler.deployments.get(str(deployment_id))
    if deployment is None:
        return None
    descriptor = deployment.metadata.model_dump()
    descriptor["task_type"] = (deployment.reference_profile or {}).get("task_type")
    descriptor["model_kind"] = detect_model_kind(deployment.manifest)
    return descriptor


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, Any]:
    asyncio.create_task(ms_handler.sync_deployments())

    yield

    data_store = getattr(app.state, "monitoring_data_store", None)
    if data_store is not None:
        await data_store.aclose()


def create_agent_app(
    authorize_access: Callable[[str], Awaitable[bool]],
    introspect_monitoring_token: IntrospectFn,
) -> FastAPI:
    app = FastAPI(lifespan=lifespan, openapi_url=None, docs_url=None, redoc_url=None)
    security = HTTPBearer()

    @app.exception_handler(DeploymentNotHostedError)
    async def deployment_not_hosted(
        request: Request, error: DeploymentNotHostedError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": error.detail, "code": error.code},
        )

    @app.exception_handler(404)
    async def unknown_route(request: Request, error: StarletteHTTPException) -> Response:
        if (
            request.url.path.startswith(MONITORING_APP_PATH)
            or request.scope.get("route") is not None
        ):
            return await http_exception_handler(request, error)
        return JSONResponse(
            status_code=404,
            content={"detail": error.detail, "code": "unknown_route"},
            headers=error.headers,
        )

    data_store = (
        GreptimeQueryStore(
            host=config.GREPTIMEDB_HOST,
            port=config.GREPTIMEDB_HTTP_PORT,
            database=config.GREPTIMEDB_DATABASE,
            profile_source=_deployment_reference_profile,
            profile_status_source=_deployment_profile_status,
            deployment_source=_deployment_descriptor,
        )
        if config.MONITORING_ENABLED
        else None
    )
    app.state.monitoring_data_store = data_store

    register_monitoring(
        app,
        introspect=introspect_monitoring_token,
        frame_ancestors=config.monitoring_frame_ancestors(),
        session_ttl_seconds=config.MONITORING_SESSION_TTL_SECONDS,
        data_store=data_store,
        health_source=_worker_health,
    )

    async def verify_token(
        credentials: HTTPAuthorizationCredentials = Depends(security),  # noqa: B008
    ) -> bool:
        try:
            authorized = await authorize_access(credentials.credentials)
            if not authorized:
                raise HTTPException(status_code=401, detail="Invalid API key")
            return True
        except HTTPException:
            raise
        except Exception as error:
            raise HTTPException(status_code=502, detail="Authorization failed") from error

    @app.post(
        INFERENCE_ACCESS_PATH,
        response_model=InferenceAccessOut,
        tags=[SATELLITE_FACET],
        summary="Check inference access",
        description="Check whether the supplied API key may call inference on this Satellite.",
    )
    async def authorize_inference_access(body: InferenceAccessIn) -> InferenceAccessOut:  # noqa: D401
        try:
            authorized = bool(await authorize_access(body.api_key))
            return InferenceAccessOut(authorized=authorized)
        except Exception as err:
            raise HTTPException(
                status_code=502, detail=f"Authorization check failed: {str(err)}"
            ) from err

    @app.get(
        "/healthz",
        response_model=Healthz,
        tags=[SATELLITE_FACET],
        summary="Check Satellite health",
        description="Report whether the Satellite Agent is running.",
        dependencies=[Depends(verify_token)],
    )
    def healthz() -> dict[str, str]:
        return {"status": "healthy"}

    @app.get(
        "/deployments",
        response_model=list[DeploymentInfo],
        tags=[DEPLOYMENT_FACET],
        summary="List hosted deployments",
        description="List active deployments hosted by this Satellite and their monitoring state.",
    )
    async def deployments(authorized: bool = Depends(verify_token)) -> list[dict]:  # noqa: B008
        local_deployments = await ms_handler.list_active_deployments()
        return [
            {
                "deployment_id": deployment.deployment_id,
                "name": deployment.metadata.name,
                "status": deployment.metadata.status,
                "monitoring_mode": "full" if deployment.monitoring_enabled else "off",
                "last_monitored_at": worker_health.snapshot(
                    deployment.deployment_id
                ).deployment.last_window_end,
            }
            for deployment in local_deployments
        ]

    app.include_router(
        build_machine_router(lambda deployment_id: str(deployment_id) in ms_handler.deployments),
        dependencies=[Depends(verify_token)],
    )

    @app.post(
        "/deployments/{deployment_id}/compute",
        response_model=dict,
        tags=[DEPLOYMENT_FACET],
        summary="Run deployment inference",
        description="Run inference using the model served by the selected deployment.",
    )
    async def compute(
        deployment_id: str,
        body: dict,
        response: Response,
        authorized: bool = Depends(verify_token),  # noqa: B008
    ) -> dict:
        try:
            result, event_id = await ms_handler.model_compute(deployment_id, body)
            if event_id:
                response.headers["X-Event-Id"] = event_id
            return result
        except ModelServerError as error:
            raise HTTPException(status_code=error.status_code, detail=error.detail) from error
        except DeploymentNotHostedError:
            raise
        except Exception as error:
            raise HTTPException(status_code=500, detail=f"Compute failed: {str(error)}") from error

    @app.get(
        "/openapi.json",
        include_in_schema=False,
        dependencies=[Depends(verify_token)],
    )
    async def openapi_json() -> JSONResponse:
        return JSONResponse(app.openapi())

    @app.get("/docs", include_in_schema=False, dependencies=[Depends(verify_token)])
    async def swagger_ui() -> HTMLResponse:
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title="Satellite Agent API - Swagger UI",
        )

    @app.get("/redoc", include_in_schema=False, dependencies=[Depends(verify_token)])
    async def redoc() -> HTMLResponse:
        return get_redoc_html(
            openapi_url="/openapi.json",
            title="Satellite Agent API - ReDoc",
        )

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        builder = OpenAPISchemaBuilder()
        openapi_schema = builder.generate_base_schema(app)
        builder.add_security_to_schema(openapi_schema)

        app.openapi_schema = openapi_handler.merge_deployment_schemas(openapi_schema)
        return app.openapi_schema

    def invalidate_openapi_cache() -> None:
        app.openapi_schema = None

    ms_handler.register_openapi_cache_invalidation_callback(invalidate_openapi_cache)

    app.openapi = custom_openapi  # type: ignore[method-assign]  # FastAPI supports overrides.
    return app
