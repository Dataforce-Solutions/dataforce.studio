from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from starlette.middleware.authentication import AuthenticationMiddleware

from dataforce_studio.api.auth import auth_router
from dataforce_studio.api.email_routes import email_routers
from dataforce_studio.api.organization.organization import organization_router
from dataforce_studio.api.organization_routes import organization_all_routers
from dataforce_studio.api.user_routes import users_routers
from dataforce_studio.infra.exceptions import ServiceError
from dataforce_studio.infra.security import JWTAuthenticationBackend


class AppService(FastAPI):
    def __init__(self, *args, **kwargs) -> None:  # type: ignore
        super().__init__(*args, **kwargs)

        self.include_router(router=auth_router, tags=["auth"])
        self.include_router(router=email_routers)
        self.include_router(router=users_routers)
        self.include_router(router=organization_router)
        self.include_router(router=organization_all_routers)
        self.include_authentication()
        self.include_error_handlers()
        self.custom_openapi()

        self.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def include_authentication(self) -> None:
        self.add_middleware(
            AuthenticationMiddleware,
            backend=JWTAuthenticationBackend(),
        )

    def include_error_handlers(self) -> None:
        @self.exception_handler(ServiceError)
        async def service_error_handler(
            request: Request,
            exc: ServiceError,
        ) -> JSONResponse:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.message},
            )

    def custom_openapi(self) -> dict:
        if self.openapi_schema:
            return self.openapi_schema
        openapi_schema = get_openapi(
            title="Dataforce Studio API",
            version="1.0.0",
            description="API docs for Dataforce Studio",
            routes=self.routes,
        )
        openapi_schema["components"]["securitySchemes"] = {
            "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
        }
        openapi_schema["security"] = [{"BearerAuth": []}]
        self.openapi_schema = openapi_schema
        return self.openapi_schema
