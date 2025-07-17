from passlib.context import CryptContext
from starlette.authentication import AuthCredentials, AuthenticationBackend
from starlette.requests import HTTPConnection

from dataforce_studio.handlers.api_keys import APIKeyHandler
from dataforce_studio.handlers.auth import AuthHandler
from dataforce_studio.infra.exceptions import AuthError
from dataforce_studio.models.auth import AuthUser
from dataforce_studio.settings import config


class JWTAuthenticationBackend(AuthenticationBackend):
    def __init__(self) -> None:
        self.auth_handler = AuthHandler(
            secret_key=config.AUTH_SECRET_KEY,
            pwd_context=CryptContext(schemes=["bcrypt"], deprecated="auto"),
        )
        self.api_key_handler = APIKeyHandler()

    async def _authenticate_with_api_key(
        self, token: str
    ) -> tuple[AuthCredentials, AuthUser] | None:
        user = await self.api_key_handler.authenticate_api_key(token)
        if user:
            auth_user = AuthUser(
                user_id=user.id,
                email=user.email,
                full_name=user.full_name,
                disabled=user.disabled,
            )
            return AuthCredentials(["authenticated", "api_key"]), auth_user
        return None

    async def _authenticate_with_jwt_token(
        self, token: str
    ) -> tuple[AuthCredentials, AuthUser] | None:
        if await self.auth_handler.is_token_blacklisted(token):
            return None

        try:
            email = self.auth_handler._verify_token(token)
            user = await self.auth_handler.handle_get_current_user(email)
            auth_user = AuthUser(
                user_id=user.id,
                email=user.email,
                full_name=user.full_name,
                disabled=user.disabled,
            )
            return AuthCredentials(["authenticated", "jwt"]), auth_user
        except AuthError:
            return None

    async def authenticate(
        self,
        conn: HTTPConnection,
    ) -> tuple[AuthCredentials, AuthUser] | None:
        authorization: str | None = conn.headers.get("Authorization")
        api_key: str | None = conn.headers.get("X-API-Key")

        if not authorization and not api_key:
            return None

        if authorization:
            try:
                scheme, token = authorization.split()
                if scheme.lower() != "bearer":
                    return None

                if token.startswith("dfs_"):
                    return await self._authenticate_with_api_key(token)
                return await self._authenticate_with_jwt_token(token)

            except ValueError:
                return None

        if api_key and api_key.startswith("dfs_"):
            return await self._authenticate_with_api_key(api_key)

        return None
