from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import EmailStr
from starlette.authentication import UnauthenticatedUser
from starlette.responses import RedirectResponse

from dataforce_studio.handlers.auth import AuthHandler
from dataforce_studio.models.auth import Token, User
from dataforce_studio.models.errors import AuthError

auth_router = APIRouter(prefix="/auth", tags=["auth"])


auth_handler = AuthHandler()


def handle_auth_error(error: AuthError) -> HTTPException:
    """Convert AuthError to FastAPI HTTPException"""
    return HTTPException(
        status_code=error.status_code,
        detail=error.message,
        headers={"WWW-Authenticate": "Bearer"} if error.status_code == 401 else None,
    )


@auth_router.post("/signup", response_model=dict)
async def signup(
    email: Annotated[EmailStr, Form()],
    password: Annotated[str, Form(min_length=8)],
    full_name: Annotated[str | None, Form()] = None,
) -> dict:
    try:
        return auth_handler.handle_signup(email, password, full_name)
    except AuthError as e:
        raise handle_auth_error(e) from e


@auth_router.post("/signin", response_model=Token)
async def signin(
    email: Annotated[EmailStr, Form()],
    password: Annotated[str, Form(min_length=8)],
) -> Token:
    try:
        return auth_handler.handle_signin(email, password)
    except AuthError as e:
        raise handle_auth_error(e) from e


@auth_router.get("/google/login")
async def google_login() -> RedirectResponse:
    params = {
        "client_id": "1005997792037-17lj55mpmh2c43b7db51jr159bneqhqr."
        "apps.googleusercontent.com",
        "redirect_uri": "https://dev.dataforce.studio/sign-in",
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return RedirectResponse(url)


@auth_router.get("/google/callback")
async def google_callback(request: Request, code: str = None) -> Token:
    if not code:
        raise HTTPException(status_code=400, detail="Missing code in callback")
    try:
        return await auth_handler.handle_google_auth(code)
    except AuthError as e:
        raise handle_auth_error(e) from e


@auth_router.post("/refresh", response_model=Token)
async def refresh(refresh_token: Annotated[str, Form()]) -> Token:
    try:
        return auth_handler.handle_refresh_token(refresh_token)
    except AuthError as e:
        raise handle_auth_error(e) from e


@auth_router.post("/forgot-password")
async def forgot_password(email: Annotated[EmailStr, Form()]) -> dict[str, str]:
    try:
        link = auth_handler.send_password_reset_email(email)
        # temp returning token for testing
    except AuthError as e:
        raise handle_auth_error(e) from e
    return {"detail": "Password reset email has been sent", "link_from_email": link}


@auth_router.get("/users/me", response_model=User)
async def get_current_user(
    request: Request,
) -> User:
    if isinstance(request.user, UnauthenticatedUser):
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        return auth_handler.handle_get_current_user(request.user.email)
    except AuthError as e:
        raise handle_auth_error(e) from e


@auth_router.delete("/users/me")
async def delete_account(
    request: Request,
) -> dict[str, str]:
    try:
        return auth_handler.handle_delete_account(request.user.email)
    except AuthError as e:
        raise handle_auth_error(e) from e


@auth_router.patch("/users/me")
async def update_user_profile(
    request: Request,
    email: Annotated[EmailStr, Form()] = None,
    full_name: Annotated[str | None, Form()] = None,
    current_password: Annotated[str | None, Form()] = None,
    new_password: Annotated[str | None, Form()] = None,
    photo: Annotated[UploadFile | None, File()] = None,
) -> dict[str, str]:
    if isinstance(request.user, UnauthenticatedUser):
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        # if email:
        #     await auth_handler.handle_update_email(email)

        if full_name:
            auth_handler.handle_change_name(request.user.email, full_name)

        if current_password and new_password:
            auth_handler.handle_change_password(
                request.user.email, current_password, new_password
            )

        # if photo:
        #     await auth_handler.handle_upload_photo(request.user.email, photo)

        return {"detail": "User profile updated successfully"}

    except AuthError as e:
        raise handle_auth_error(e) from e


@auth_router.delete("/users/me/photo")
async def delete_user_photo(
    request: Request,
) -> dict[str, str]:
    """
    Delete the user's current profile photo.
    """
    if isinstance(request.user, UnauthenticatedUser):
        raise HTTPException(status_code=401, detail="Not authenticated")

    # try:
    #     return auth_handler.handle_delete_photo(request.user.email)
    # except AuthError as e:
    #     raise handle_auth_error(e) from e

    return {"detail": "Photo successfully deleted"}


@auth_router.post("/logout")
async def logout(
    request: Request,
    refresh_token: Annotated[str, Form()],
) -> dict[str, str]:
    try:
        auth_header = request.headers.get("Authorization")
        access_token = auth_header.split()[1] if auth_header else None
        return auth_handler.handle_logout(access_token, refresh_token)
    except AuthError as e:
        raise handle_auth_error(e) from e


@auth_router.get("/confirm-email")
async def confirm_email(
    confirmation_token: str,
) -> RedirectResponse:
    try:
        auth_handler.handle_email_confirmation(confirmation_token)
        return RedirectResponse("http://localhost:5173/email-confirmed")
    except AuthError as e:
        raise handle_auth_error(e) from e


@auth_router.post("/reset-password")
async def reset_password(
    reset_token: Annotated[str, Form()],
    new_password: Annotated[str, Form(min_length=8)],
) -> dict[str, str]:
    try:
        return auth_handler.handle_reset_password(reset_token, new_password)
    except AuthError as e:
        raise handle_auth_error(e) from e
