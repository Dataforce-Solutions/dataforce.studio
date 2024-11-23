from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from handlers.auth import AuthHandler
from infra.security import oauth2_scheme
from models.auth import Token, User
from models.errors import AuthError
from pydantic import EmailStr

auth_router = APIRouter(prefix="/auth", tags=["auth"])


auth_handler = AuthHandler()


def handle_auth_error(error: AuthError) -> HTTPException:
    """Convert AuthError to FastAPI HTTPException"""
    return HTTPException(
        status_code=error.status_code,
        detail=error.message,
        headers={"WWW-Authenticate": "Bearer"} if error.status_code == 401 else None,
    )


@auth_router.post("/signup", response_model=Token)
async def signup(
    email: Annotated[EmailStr, Form()],
    password: Annotated[str, Form()],
    full_name: Annotated[str | None, Form()] = None,
) -> Token:
    try:
        return auth_handler.handle_signup(email, password, full_name)
    except AuthError as e:
        raise handle_auth_error(e) from e


@auth_router.post("/signin", response_model=Token)
async def signin(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> Token:
    try:
        return auth_handler.handle_signin(form_data.username, form_data.password)
    except AuthError as e:
        raise handle_auth_error(e) from e


@auth_router.post("/refresh", response_model=Token)
async def refresh_token(refresh_request: Annotated[str, Form()]) -> Token:
    try:
        return auth_handler.handle_refresh_token(refresh_request)
    except AuthError as e:
        raise handle_auth_error(e) from e


@auth_router.post("/change-password")
async def change_password(
    request: Request,
    current_password: Annotated[str, Form()],
    new_password: Annotated[str, Form()],
    _: str = Annotated[oauth2_scheme, Depends()],
) -> dict[str, str]:
    try:
        return auth_handler.handle_change_password(
            request.user.email, current_password, new_password
        )
    except AuthError as e:
        raise handle_auth_error(e) from e


@auth_router.delete("/delete-account")
async def delete_account(
    request: Request,
    _: str = Annotated[oauth2_scheme, Depends()],
) -> dict[str, str]:
    try:
        return auth_handler.handle_delete_account(request.user.email)
    except AuthError as e:
        raise handle_auth_error(e) from e


@auth_router.get("/me", response_model=User)
async def get_current_user(
    request: Request,
    _: str = Annotated[oauth2_scheme, Depends()],
) -> User:
    try:
        return auth_handler.handle_get_current_user(request.user.email)
    except AuthError as e:
        raise handle_auth_error(e) from e


@auth_router.post("/logout")
async def logout(
    request: Request,
    refresh_token: Annotated[str, Form()],
    _: str = Annotated[oauth2_scheme, Depends()],
) -> dict[str, str]:
    try:
        auth_header = request.headers.get("Authorization")
        access_token = auth_header.split()[1] if auth_header else None
        return auth_handler.handle_logout(access_token, refresh_token)
    except AuthError as e:
        raise handle_auth_error(e) from e
