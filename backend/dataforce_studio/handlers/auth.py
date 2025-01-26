from time import time

import httpx
import jwt
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext

from dataforce_studio.handlers.emails import EmailHandler
from dataforce_studio.models.auth import (
    AuthProvider,
    Token,
    User,
)
from dataforce_studio.models.errors import AuthError
from dataforce_studio.repositories.token_blacklist import TokenBlackListRepository
from dataforce_studio.repositories.users import UserRepository
from dataforce_studio.settings import config


class AuthHandler:
    __user_repository = UserRepository()
    __token_black_list_repository = TokenBlackListRepository()
    __emails_handler = EmailHandler()

    def __init__(
        self,
        secret_key: str,
        pwd_context: CryptContext,
        algorithm: str = "HS256",
        access_token_expire: int = 10800,  # 3 hours
        refresh_token_expire: int = 604800,  # 7 days
    ) -> None:
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire = access_token_expire
        self.refresh_token_expire = refresh_token_expire
        self.pwd_context = pwd_context

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return self.pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        return self.pwd_context.hash(password)

    async def authenticate_user(self, email: str, password: str) -> User:
        service_user = await self.__user_repository.get_user(email)
        if not service_user or not self.verify_password(
            password, service_user.hashed_password
        ):
            raise AuthError("Invalid email or password", 400)
        if not service_user.email_verified:
            raise AuthError("Email not verified", 400)
        if service_user.auth_method != AuthProvider.EMAIL:
            raise AuthError("Invalid auth method", 400)
        return service_user.to_user()

    def create_token(self, data: dict, expires_delta: int) -> str:
        to_encode = data.copy()
        expire = int(time()) + expires_delta
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    def create_tokens(self, user_email: str) -> Token:
        access_token = self.create_token(
            data={"sub": user_email},
            expires_delta=self.access_token_expire,
        )
        refresh_token = self.create_token(
            data={"sub": user_email, "type": "refresh"},
            expires_delta=self.refresh_token_expire,
        )
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
        )

    def verify_token(self, token: str) -> str:
        """Verify a token and return the user email"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            email: str = payload.get("sub")
            if email is None:
                raise AuthError("Invalid token", 401)
            return email
        except InvalidTokenError as err:
            raise AuthError("Invalid token", 401) from err

    async def handle_signup(
        self, email: str, password: str, full_name: str | None = None
    ) -> dict:
        """Handle user signup process"""
        if (
            user := await self.__user_repository.get_user(email)
        ) and user.email_verified:
            raise AuthError("Email already registered", 400)
        if not user:
            if not password:
                raise AuthError("Password is required", 400)

            hashed_password = self.get_password_hash(password)

            await self.__user_repository.create_user(
                email=email,
                full_name=full_name,
                disabled=False,
                email_verified=False,
                hashed_password=hashed_password,
                auth_method=AuthProvider.EMAIL,
                photo=None,
            )
        confirmation_token = self._generate_email_confirmation_token(email)
        confirmation_link = self._get_email_confirmation_link(confirmation_token)
        self.__emails_handler.send_activation_email(email, confirmation_link, full_name)
        return {"detail": "Please confirm your email address"}

    def _get_email_confirmation_link(self, token: str) -> str:
        return config.CONFIRM_EMAIL_URL + token

    async def handle_signin(self, email: str, password: str) -> Token:
        """Handle user signin process"""
        user = await self.authenticate_user(email, password)
        return self.create_tokens(user.email)

    async def handle_refresh_token(self, refresh_token: str) -> Token:
        """Handle token refresh process"""
        try:
            payload = jwt.decode(
                refresh_token, self.secret_key, algorithms=[self.algorithm]
            )

            if payload.get("type") != "refresh":
                raise AuthError("Invalid token type", 400)

            email: str = payload.get("sub")
            if email is None:
                raise AuthError("Invalid token", 400)

            if await self.__token_black_list_repository.is_token_blacklisted(
                refresh_token
            ):
                raise AuthError("Token has been revoked", 400)

            if service_user := await self.__user_repository.get_user(email) is None:
                raise AuthError("User not found", 404)

            exp = int(payload.get("exp"))

            await self.__token_black_list_repository.add_token(refresh_token, exp)

            return self.create_tokens(service_user.email)

        except InvalidTokenError as err:
            raise AuthError("Invalid refresh token", 400) from err

    async def handle_change_password(
        self,
        email: str,
        current_password: str,
        new_password: str,
    ) -> dict[str, str]:
        """Handle password change process"""
        if not (service_user := await self.__user_repository.get_user(email)):
            raise AuthError("User not found", 404)

        if not self.verify_password(current_password, service_user.hashed_password):
            raise AuthError("Invalid current password", 400)

        await self.__user_repository.update_user(
            email,
            hashed_password=self.get_password_hash(new_password),
        )
        return {"detail": "Password changed successfully"}

    async def handle_change_name(
        self,
        email: str,
        new_name: str,
    ) -> None:
        """Handle password change process"""
        if not (service_user := await self.__user_repository.get_user(email)):
            raise AuthError("User not found", 404)

        await self.__user_repository.update_user(service_user.email, full_name=new_name)

    async def handle_delete_account(self, email: str) -> None:
        """Handle account deletion process"""
        await self.__user_repository.delete_user(email)

    async def handle_get_current_user(self, email: str) -> User:
        """Handle getting current user information"""
        if not (service_user := await self.__user_repository.get_user(email)):
            raise AuthError("User not found", 404)

        if service_user.disabled:
            raise AuthError("Account is disabled", 400)

        return service_user.to_user()

    async def handle_logout(self, access_token: str, refresh_token: str) -> None:
        """Handle logout process"""
        try:
            payload = jwt.decode(
                refresh_token, self.secret_key, algorithms=[self.algorithm]
            )
            exp = payload.get("exp")

            if access_token:
                try:
                    access_payload = jwt.decode(
                        access_token, self.secret_key, algorithms=[self.algorithm]
                    )
                    exp = access_payload.get("exp")
                    await self.__token_black_list_repository.add_token(
                        access_token, exp
                    )
                except InvalidTokenError:
                    pass

            await self.__token_black_list_repository.add_token(refresh_token, exp)

        except InvalidTokenError as err:
            raise AuthError("Invalid refresh token", 400) from err

    async def handle_google_auth(self, code: str) -> Token:
        data = {
            "code": code,
            "client_id": config.GOOGLE_CLIENT_ID,
            "client_secret": config.GOOGLE_CLIENT_SECRET,
            "redirect_uri": config.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }

        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token", data=data
            )
            if token_response.status_code != 200:
                raise AuthError("Failed to retrieve token from Google", 400)

            token_data = token_response.json()
            access_token = token_data.get("access_token")
            if not access_token:
                raise AuthError("Failed to retrieve access token", 400)

            userinfo_response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if userinfo_response.status_code != 200:
                raise AuthError("Failed to retrieve user info from Google", 400)

        userinfo = userinfo_response.json()
        email = userinfo.get("email")
        full_name = userinfo.get("name")
        photo_url = userinfo.get("picture")

        if not email:
            raise AuthError("Failed to retrieve user email", 400)

        service_user = await self.__user_repository.get_user(email)
        if service_user and service_user.auth_method != AuthProvider.GOOGLE:
            await self.__user_repository.update_user(
                email,
                auth_provider=AuthProvider.GOOGLE,
                email_verified=True,
                hashed_password="reset",
                photo=photo_url,
            )
        if not service_user:
            service_user = await self.__user_repository.create_user(
                email=email,
                full_name=full_name,
                disabled=False,
                email_verified=True,
                auth_method=AuthProvider.GOOGLE,
                photo=photo_url,
            )

        if photo_url != service_user.photo:
            await self.__user_repository.update_user(email, photo=photo_url)

        return self.create_tokens(service_user.email)

    def _generate_email_confirmation_token(self, email: str) -> str:
        return self.create_token(
            data={"sub": email, "type": "email_confirmation"},
            expires_delta=86400,  # 24 hours
        )

    def _generate_password_reset_token(self, email: str) -> str:
        return self.create_token(
            data={"sub": email, "type": "password_reset"},
            expires_delta=3600,  # 1 hour
        )

    async def send_password_reset_email(self, email: str) -> None:
        if not (service_user := await self.__user_repository.get_user(email)):
            return
        token = self._generate_password_reset_token(service_user.email)
        link = self._get_password_reset_link(token)
        self.__emails_handler.send_password_reset_email(email, link)

    def _get_password_reset_link(self, token: str) -> str:
        return config.CHANGE_PASSWORD_URL + token

    async def handle_email_confirmation(self, token: str) -> None:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            email: str = payload.get("sub")
        except InvalidTokenError as err:
            raise AuthError("Invalid token", 400) from err
        if email is None:
            raise AuthError("Invalid token", 400)

        if (service_user := await self.__user_repository.get_user(email)) is None:
            raise AuthError("User not found", 404)

        if service_user.email_verified:
            raise AuthError("Email already verified", 400)

        await self.__user_repository.update_user(
            service_user.email, email_verified=True
        )

    async def handle_reset_password(self, token: str, new_password: str) -> None:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            email: str = payload.get("sub")
            exp = payload.get("exp")
            if exp is None or exp < time():
                raise AuthError("Token expired", 400)
            if email is None:
                raise AuthError("Invalid token", 400)

            if (service_user := await self.__user_repository.get_user(email)) is None:
                raise AuthError("User not found", 404)

            await self.__user_repository.update_user(
                service_user.email, hashed_password=self.get_password_hash(new_password)
            )
        except InvalidTokenError as err:
            raise AuthError("Invalid token", 400) from err

    async def is_token_blacklisted(self, token: str) -> bool:
        return await self.__token_black_list_repository.is_token_blacklisted(token)
