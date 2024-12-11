from datetime import UTC, datetime, timedelta

import httpx
import jwt
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext

from dataforce_studio.models.auth import AuthProvider, Token, User, UserInDB
from dataforce_studio.models.errors import AuthError
from dataforce_studio.repositories.token_blacklist import token_blacklist
from dataforce_studio.repositories.users import fake_users_db


class AuthHandler:
    __secret_key = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
    __pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def __init__(
        self,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 180,
        refresh_token_expire_days: int = 7,
    ) -> None:
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return self.__pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        return self.__pwd_context.hash(password)

    def get_user(self, email: str) -> UserInDB | None:
        if email in fake_users_db:
            user_dict = fake_users_db[email]
            return UserInDB(**user_dict)
        return None

    def authenticate_user(self, email: str, password: str) -> UserInDB | None:
        user = self.get_user(email)
        if not user or not self.verify_password(password, user.hashed_password):
            return None
        if user.auth_method != AuthProvider.EMAIL:
            raise AuthError("Invalid auth method", 400)
        return user

    def create_token(self, data: dict, expires_delta: timedelta) -> str:
        to_encode = data.copy()
        expire = datetime.now(UTC) + expires_delta
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, self.__secret_key, algorithm=self.algorithm)

    def create_tokens(self, user_email: str) -> Token:
        access_token = self.create_token(
            data={"sub": user_email},
            expires_delta=timedelta(minutes=self.access_token_expire_minutes),
        )
        refresh_token = self.create_token(
            data={"sub": user_email, "type": "refresh"},
            expires_delta=timedelta(days=self.refresh_token_expire_days),
        )
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
        )

    def is_token_blacklisted(self, token: str) -> bool:
        return token in token_blacklist

    def blacklist_token(self, token: str, expires: datetime) -> None:
        token_blacklist[token] = expires

    def verify_token(self, token: str) -> str:
        """Verify a token and return the user email"""
        try:
            payload = jwt.decode(token, self.__secret_key, algorithms=[self.algorithm])
            email: str = payload.get("sub")
            if email is None:
                raise AuthError("Invalid token", 401)
            return email
        except InvalidTokenError as err:
            raise AuthError("Invalid token", 401) from err

    def handle_signup(
        self, email: str, password: str, full_name: str | None = None
    ) -> Token:
        """Handle user signup process"""
        if fake_users_db.get(email):
            raise AuthError("Email already registered", 400)

        if not password:
            raise AuthError("Password is required", 400)

        hashed_password = self.get_password_hash(password)
        user = UserInDB(
            email=email,
            full_name=full_name,
            disabled=False,
            hashed_password=hashed_password,
            auth_method=AuthProvider.EMAIL,
        )
        fake_users_db[email] = user.model_dump()

        return self.create_tokens(user.email)

    def handle_signin(self, email: str, password: str) -> Token:
        """Handle user signin process"""
        user = self.authenticate_user(email, password)
        if not user:
            raise AuthError("Invalid email or password", 400)
        return self.create_tokens(user.email)

    def handle_refresh_token(self, refresh_token: str) -> Token:
        """Handle token refresh process"""
        try:
            payload = jwt.decode(
                refresh_token, self.__secret_key, algorithms=[self.algorithm]
            )

            if payload.get("type") != "refresh":
                raise AuthError("Invalid token type", 400)

            email: str = payload.get("sub")
            if email is None:
                raise AuthError("Invalid token", 400)

            if self.is_token_blacklisted(refresh_token):
                raise AuthError("Token has been revoked", 400)

            user = self.get_user(email)
            if user is None:
                raise AuthError("User not found", 404)

            token_expiry = datetime.fromtimestamp(payload["exp"], tz=UTC)
            self.blacklist_token(refresh_token, token_expiry)

            return self.create_tokens(email)

        except InvalidTokenError as err:
            raise AuthError("Invalid refresh token", 400) from err

    def handle_change_password(
        self,
        email: str,
        current_password: str,
        new_password: str,
    ) -> dict[str, str]:
        """Handle password change process"""
        user = self.get_user(email)
        if not user:
            raise AuthError("User not found", 404)

        if not self.verify_password(current_password, user.hashed_password):
            raise AuthError("Invalid current password", 400)

        fake_users_db[user.email]["hashed_password"] = self.get_password_hash(
            new_password
        )
        return {"detail": "Password changed successfully"}

    def handle_change_name(
        self,
        email: str,
        new_name: str,
    ) -> dict[str, str]:
        """Handle password change process"""
        user = self.get_user(email)
        if not user:
            raise AuthError("User not found", 404)

        fake_users_db[user.email]["full_name"] = new_name
        return {"detail": "Name changed successfully"}

    def handle_delete_account(self, email: str) -> dict[str, str]:
        """Handle account deletion process"""
        if email in fake_users_db:
            del fake_users_db[email]
            return {"detail": "Account deleted successfully"}

        raise AuthError("User not found", 404)

    def handle_get_current_user(self, email: str) -> User:
        """Handle getting current user information"""
        user_in_db = self.get_user(email)
        if user_in_db is None:
            raise AuthError("User not found", 404)

        if user_in_db.disabled:
            raise AuthError("Account is disabled", 400)

        return User(
            email=user_in_db.email,
            full_name=user_in_db.full_name,
            disabled=user_in_db.disabled,
            auth_method=user_in_db.auth_method,
            photo=user_in_db.photo,
        )

    def handle_logout(self, access_token: str, refresh_token: str) -> dict[str, str]:
        """Handle logout process"""
        try:
            payload = jwt.decode(
                refresh_token, self.__secret_key, algorithms=[self.algorithm]
            )
            token_expiry = datetime.fromtimestamp(payload["exp"], tz=UTC)

            if access_token:
                try:
                    access_payload = jwt.decode(
                        access_token, self.__secret_key, algorithms=[self.algorithm]
                    )
                    access_expiry = datetime.fromtimestamp(
                        access_payload["exp"], tz=UTC
                    )
                    self.blacklist_token(access_token, access_expiry)
                except InvalidTokenError:
                    pass

            self.blacklist_token(refresh_token, token_expiry)
            return {"detail": "Successfully logged out"}

        except InvalidTokenError as err:
            raise AuthError("Invalid refresh token", 400) from err

    async def handle_google_auth(self, code: str) -> Token:
        data = {
            "code": code,
            "client_id": "1005997792037-17lj55mpmh2c43b7db51jr159bneqhqr."
            "apps.googleusercontent.com",
            "client_secret": "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",
            "redirect_uri": "http://localhost:5173/sign-in",
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

        user = self.get_user(email)
        if (not user) or (user.auth_method != AuthProvider.GOOGLE):
            user = UserInDB(
                email=email,
                full_name=full_name,
                disabled=False,
                hashed_password=None,
                photo=photo_url,
                auth_method=AuthProvider.GOOGLE,
            )
            fake_users_db[email] = user.model_dump()

        return self.create_tokens(email)
