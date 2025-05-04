from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Form, HTTPException, Request
from passlib.context import CryptContext
from pydantic import EmailStr
from starlette.authentication import UnauthenticatedUser
from starlette.responses import RedirectResponse

from dataforce_studio.handlers.auth import AuthHandler
from dataforce_studio.models.auth import Token
from dataforce_studio.models.errors import AuthError
from dataforce_studio.models.user import CreateUserIn, UpdateUserIn, User
from dataforce_studio.settings import config

auth_router = APIRouter(prefix="/auth", tags=["auth"])


auth_handler = AuthHandler(
    secret_key=config.AUTH_SECRET_KEY,
    pwd_context=CryptContext(schemes=["bcrypt"], deprecated="auto"),
)


def handle_auth_error(error: AuthError) -> HTTPException:
    """Convert AuthError to FastAPI HTTPException"""
    return HTTPException(
        status_code=error.status_code,
        detail=error.message,
        headers={"WWW-Authenticate": "Bearer"} if error.status_code == 401 else None,
    )


@auth_router.post("/signup", response_model=dict)
async def signup(create_user: CreateUserIn) -> dict[str, str]:
    try:
        return await auth_handler.handle_signup(create_user)
    except AuthError as e:
        raise handle_auth_error(e) from e


@auth_router.post("/signin", response_model=Token)
async def signin(
    email: Annotated[EmailStr, Form()],
    password: Annotated[str, Form(min_length=8)],
) -> Token:
    try:
        return await auth_handler.handle_signin(email, password)
    except AuthError as e:
        raise handle_auth_error(e) from e


@auth_router.get("/google/login")
async def google_login() -> RedirectResponse:
    params = {
        "client_id": config.GOOGLE_CLIENT_ID,
        "redirect_uri": config.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return RedirectResponse(url)


@auth_router.get("/google/callback")
async def google_callback(request: Request, code: str | None = None) -> Token:
    if not code:
        raise HTTPException(status_code=400, detail="Missing code in callback")
    try:
        return await auth_handler.handle_google_auth(code)
    except AuthError as e:
        raise handle_auth_error(e) from e


@auth_router.post("/refresh", response_model=Token)
async def refresh(refresh_token: Annotated[str, Form()]) -> Token:
    try:
        return await auth_handler.handle_refresh_token(refresh_token)
    except AuthError as e:
        raise handle_auth_error(e) from e


@auth_router.post("/forgot-password")
async def forgot_password(email: Annotated[EmailStr, Form()]) -> dict[str, str]:
    try:
        await auth_handler.send_password_reset_email(email)
    except AuthError as e:
        raise handle_auth_error(e) from e
    return {"detail": "Password reset email has been sent"}


@auth_router.get("/users/me", response_model=User)
async def get_current_user(
    request: Request,
) -> User:
    if isinstance(request.user, UnauthenticatedUser):
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        return await auth_handler.handle_get_current_user(request.user.email)
    except AuthError as e:
        raise handle_auth_error(e) from e


@auth_router.delete("/users/me")
async def delete_account(
    request: Request,
) -> dict[str, str]:
    try:
        await auth_handler.handle_delete_account(request.user.email)
        return {"detail": "Account deleted successfully"}
    except AuthError as e:
        raise handle_auth_error(e) from e


@auth_router.patch("/users/me")
async def update_user_profile(
    request: Request,
    update_user: UpdateUserIn,
) -> dict[str, str]:
    if isinstance(request.user, UnauthenticatedUser):
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        return {
            "detail": "User profile updated successfully"
            if (await auth_handler.update_user(request.user.email, update_user))
            else "No changes made to the user profile"
        }
    except AuthError as e:
        raise handle_auth_error(e) from e


@auth_router.post("/logout")
async def logout(
    request: Request,
    refresh_token: Annotated[str, Form()],
) -> dict[str, str]:
    try:
        auth_header = request.headers.get("Authorization")
        access_token = auth_header.split()[1] if auth_header else None
        await auth_handler.handle_logout(access_token, refresh_token)
        return {"detail": "Successfully logged out"}
    except AuthError as e:
        raise handle_auth_error(e) from e


@auth_router.get("/confirm-email")
async def confirm_email(
    confirmation_token: str,
) -> RedirectResponse:
    try:
        await auth_handler.handle_email_confirmation(confirmation_token)
        return RedirectResponse(config.CONFIRM_EMAIL_REDIRECT_URL)
    except AuthError as e:
        raise handle_auth_error(e) from e


@auth_router.post("/reset-password")
async def reset_password(
    reset_token: Annotated[str, Form()],
    new_password: Annotated[str, Form(min_length=8)],
) -> dict[str, str]:
    try:
        await auth_handler.handle_reset_password(reset_token, new_password)
        return {"detail": "Password reset successfully"}
    except AuthError as e:
        raise handle_auth_error(e) from e
