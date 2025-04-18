from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.authentication import AuthenticationMiddleware

from dataforce_studio.api.auth import auth_router
from dataforce_studio.infra.security import JWTAuthenticationBackend


class AppService(FastAPI):
    def __init__(self, *args, **kwargs) -> None:  # type: ignore
        super().__init__(*args, **kwargs)

        self.include_router(router=auth_router, tags=["auth"])
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
