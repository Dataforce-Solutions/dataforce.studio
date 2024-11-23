from fastapi.security import OAuth2PasswordBearer
from handlers.auth import AuthHandler
from models.auth import AuthUser
from models.errors import AuthError
from starlette.authentication import AuthCredentials, AuthenticationBackend
from starlette.requests import HTTPConnection

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/signin", scheme_name="JWT")


class JWTAuthenticationBackend(AuthenticationBackend):
    def __init__(self) -> None:
        self.auth_handler = AuthHandler()

    async def authenticate(
        self,
        conn: HTTPConnection,
    ) -> tuple[AuthCredentials, AuthUser] | None:
        authorization: str = conn.headers.get("Authorization")
        if not authorization:
            return None

        try:
            scheme, token = authorization.split()
            if scheme.lower() != "bearer":
                return None

            if self.auth_handler.is_token_blacklisted(token):
                return None

            try:
                email = self.auth_handler.verify_token(token)
            except AuthError:
                return None

            try:
                user = self.auth_handler.handle_get_current_user(email)
                auth_user = AuthUser(
                    email=user.email,
                    full_name=user.full_name,
                    disabled=user.disabled,
                )
                return AuthCredentials(["authenticated"]), auth_user
            except AuthError:
                return None

        except ValueError:
            return None
