from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.authentication import AuthenticationMiddleware

from dataforce_studio.api.auth import auth_router
from dataforce_studio.api.organization import organization_router
from dataforce_studio.infra.exceptions import ServiceError
from dataforce_studio.api.organization_invites import invites_router
from dataforce_studio.api.organization_members import members_router
from dataforce_studio.infra.security import JWTAuthenticationBackend


class AppService(FastAPI):
    def __init__(self, *args, **kwargs) -> None:  # type: ignore
        super().__init__(*args, **kwargs)

        self.include_router(router=auth_router, tags=["auth"])
        self.include_router(router=organization_router)
        self.include_router(router=invites_router)
        self.include_router(router=members_router)
        self.include_authentication()

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
