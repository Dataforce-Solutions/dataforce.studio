from passlib.context import CryptContext
from starlette.authentication import AuthCredentials, AuthenticationBackend
from starlette.requests import HTTPConnection

from dataforce_studio.handlers.auth import AuthHandler
from dataforce_studio.models.auth import AuthUser
from dataforce_studio.models.errors import AuthError
from dataforce_studio.settings import config


class JWTAuthenticationBackend(AuthenticationBackend):
    def __init__(self) -> None:
        self.auth_handler = AuthHandler(
            secret_key=config.AUTH_SECRET_KEY,
            pwd_context=CryptContext(schemes=["bcrypt"], deprecated="auto"),
        )

    async def authenticate(
        self,
        conn: HTTPConnection,
    ) -> tuple[AuthCredentials, AuthUser] | None:
        authorization: str | None = conn.headers.get("Authorization")
        if not authorization:
            return None

        try:
            scheme, token = authorization.split()
            if scheme.lower() != "bearer":
                return None

            if await self.auth_handler.is_token_blacklisted(token):
                return None

            try:
                email = self.auth_handler._verify_token(token)
            except AuthError:
                return None

            try:
                user = await self.auth_handler.handle_get_current_user(email)
                auth_user = AuthUser(
                    user_id=user.id,
                    email=user.email,
                    full_name=user.full_name,
                    disabled=user.disabled,
                )
                return AuthCredentials(["authenticated"]), auth_user
            except AuthError:
                return None

        except ValueError:
            return None
