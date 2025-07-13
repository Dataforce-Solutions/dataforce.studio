from time import time
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import jwt
import pytest
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext

from dataforce_studio.handlers.auth import AuthHandler
from dataforce_studio.infra.exceptions import AuthError
from dataforce_studio.models.auth import Token
from dataforce_studio.schemas.user import (
    AuthProvider,
    CreateUser,
    CreateUserIn,
    UpdateUser,
    UpdateUserIn,
    User,
    UserOut,
)

secret_key = "test"
algorithm = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

handler = AuthHandler(
    secret_key=secret_key, algorithm=algorithm, pwd_context=pwd_context
)

passwords = {
    "password": "test_password",
    "hashed_password": "$2b$12$rr/FMTnWz0BGDTiG//l.YuzZe9ZIpZTPZD5FeAVDDdqgchIDUyD66",
}


@patch("passlib.context.CryptContext.hash")
def test_get_password_hash(patched_hash: Mock) -> None:
    patched_hash.return_value = passwords["hashed_password"]

    hashed_password_from_auth_handler = handler._get_password_hash(
        passwords["password"]
    )
    assert passwords["hashed_password"] == hashed_password_from_auth_handler


@patch("passlib.context.CryptContext.verify")
def test_verify_password(mock_verify: Mock) -> None:
    mock_verify.return_value = True

    actual = handler._verify_password(
        passwords["password"], passwords["hashed_password"]
    )

    assert actual
    mock_verify.assert_called_once_with(
        passwords["password"], passwords["hashed_password"]
    )


@patch("passlib.context.CryptContext.verify")
@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_authenticate_user(mock_get_user: AsyncMock, mock_verify: Mock) -> None:
    expected = User(
        id=1,
        email="testuser@example.com",
        full_name="Test User",
        disabled=False,
        email_verified=True,
        auth_method=AuthProvider.EMAIL,
        photo=None,
        hashed_password=passwords["hashed_password"],
    )

    mock_verify.return_value = True
    mock_get_user.return_value = expected

    actual = await handler._authenticate_user(expected.email, passwords["password"])

    assert actual == expected
    mock_get_user.assert_awaited_once_with(expected.email)
    mock_verify.assert_called_once_with(passwords["password"], expected.hashed_password)


@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_authenticate_user_user_not_found(mock_get_user: AsyncMock) -> None:
    test_email = "testuser@example.com"

    mock_get_user.return_value = None

    with pytest.raises(AuthError, match="Invalid email or password") as error:
        await handler._authenticate_user(test_email, passwords["password"])

    assert error.value.status_code == 400
    mock_get_user.assert_awaited_once_with(test_email)


@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_authenticate_user_invalid_auth_method(mock_get_user: AsyncMock) -> None:
    expected = User(
        id=1,
        email="testuser@example.com",
        full_name="Test User",
        disabled=False,
        email_verified=True,
        auth_method=AuthProvider.GOOGLE,
        photo=None,
        hashed_password=passwords["hashed_password"],
    )
    mock_get_user.return_value = expected

    with pytest.raises(AuthError, match="Invalid auth method") as error:
        await handler._authenticate_user(expected.email, passwords["password"])

    assert error.value.status_code == 400
    mock_get_user.assert_awaited_once_with(expected.email)


@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_authenticate_user_password_is_invalid(mock_get_user: AsyncMock) -> None:
    expected = User(
        id=1,
        email="testuser@example.com",
        full_name="Test User",
        disabled=False,
        email_verified=True,
        auth_method=AuthProvider.EMAIL,
        photo=None,
        hashed_password=None,
    )
    mock_get_user.return_value = expected

    with pytest.raises(AuthError, match="Password is invalid") as error:
        await handler._authenticate_user(expected.email, passwords["password"])

    assert error.value.status_code == 400
    mock_get_user.assert_awaited_once_with(expected.email)


@patch("passlib.context.CryptContext.verify")
@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_authenticate_user_password_not_verified(
    mock_get_user: AsyncMock, mock_verify: Mock
) -> None:
    expected = User(
        id=1,
        email="testuser@example.com",
        full_name="Test User",
        disabled=False,
        email_verified=True,
        auth_method=AuthProvider.EMAIL,
        photo=None,
        hashed_password=passwords["hashed_password"],
    )

    mock_verify.return_value = False
    mock_get_user.return_value = expected

    with pytest.raises(AuthError, match="Invalid email or password") as error:
        await handler._authenticate_user(expected.email, passwords["password"])

    assert error.value.status_code == 400
    mock_get_user.assert_awaited_once_with(expected.email)


@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_authenticate_user_email_not_verified(mock_get_user: AsyncMock) -> None:
    expected = User(
        id=1,
        email="testuser@example.com",
        full_name="Test User",
        disabled=False,
        email_verified=False,
        auth_method=AuthProvider.EMAIL,
        photo=None,
        hashed_password=passwords["hashed_password"],
    )
    mock_get_user.return_value = expected

    with pytest.raises(AuthError, match="Email not verified") as error:
        await handler._authenticate_user(expected.email, passwords["password"])

    assert error.value.status_code == 400
    mock_get_user.assert_awaited_once_with(expected.email)


@pytest.mark.asyncio
async def test_create_tokens() -> None:
    test_email = "testuser@example.com"
    actual = handler._create_tokens(test_email)

    assert actual
    assert actual.access_token
    assert actual.refresh_token
    assert actual.token_type == "bearer"


@patch("dataforce_studio.handlers.auth.jwt.decode")
def test_verify_token_valid(mock_jwt_decode: MagicMock) -> None:
    test_email = "testuser@example.com"
    mock_jwt_decode.return_value = {"sub": test_email}

    actual = handler._verify_token("token")

    assert actual == test_email
    mock_jwt_decode.assert_called_once()


@patch("dataforce_studio.handlers.auth.jwt.decode")
def test_verify_token_cant_get_email(mock_jwt_decode: MagicMock) -> None:
    mock_jwt_decode.return_value = {"sub": None}

    with pytest.raises(AuthError, match="Invalid token") as exc_info:
        handler._verify_token("invalid_token")

    assert exc_info.value.status_code == 401
    mock_jwt_decode.assert_called_once()


@patch("dataforce_studio.handlers.auth.jwt.decode")
def test_verify_token_invalid_jwt(mock_jwt_decode: MagicMock) -> None:
    mock_jwt_decode.side_effect = InvalidTokenError()

    with pytest.raises(AuthError, match="Invalid token") as exc_info:
        handler._verify_token("invalid_token")

    assert exc_info.value.status_code == 401
    mock_jwt_decode.assert_called_once()


@patch("passlib.context.CryptContext.hash")
@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@patch(
    "dataforce_studio.handlers.auth.UserRepository.create_user", new_callable=AsyncMock
)
@patch(
    "dataforce_studio.handlers.auth.EmailHandler.send_activation_email",
    new_callable=MagicMock,
)
@pytest.mark.asyncio
async def test_handle_signup(
    mock_send_activation_email: MagicMock,
    mock_create_user: AsyncMock,
    mock_get_user: AsyncMock,
    mock_hash: Mock,
) -> None:
    create_user_in = CreateUserIn(
        email="testuser@example.com",
        password="test_password",
        full_name="Test User",
    )
    create_user = CreateUser(
        **create_user_in.model_dump(exclude={"password"}),
        hashed_password=passwords["hashed_password"],
        auth_method=AuthProvider.EMAIL,
    )
    mock_get_user.return_value = None
    mock_hash.return_value = passwords["hashed_password"]

    actual = await handler.handle_signup(create_user_in)

    assert actual
    assert actual["detail"] == "Please confirm your email address"
    mock_send_activation_email.assert_called_once()
    mock_hash.assert_called_once_with(create_user_in.password)
    mock_get_user.assert_awaited_once_with(create_user.email)
    mock_create_user.assert_awaited_once_with(create_user=create_user)


@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_handle_signup_already_exist(mock_get_user: AsyncMock) -> None:
    create_user_in = CreateUserIn(
        email="testuser@example.com",
        password="test_password",
        full_name="Test User",
    )
    user = User(
        id=1,
        email="testuser@example.com",
        full_name="Test User",
        disabled=False,
        email_verified=True,
        auth_method=AuthProvider.EMAIL,
        photo=None,
        hashed_password=passwords["hashed_password"],
    )
    create_user = CreateUser(
        **create_user_in.model_dump(exclude={"password"}),
        hashed_password=passwords["hashed_password"],
        auth_method=AuthProvider.EMAIL,
    )
    mock_get_user.return_value = user

    with pytest.raises(AuthError, match="Email already registered") as error:
        await handler.handle_signup(create_user_in)

    assert error.value.status_code == 400
    mock_get_user.assert_awaited_once_with(create_user.email)


@patch.object(AuthHandler, "_authenticate_user", new_callable=AsyncMock)
@patch.object(AuthHandler, "_create_tokens", new_callable=MagicMock)
@pytest.mark.asyncio
async def test_handle_signin(
    mock_create_tokens: MagicMock,
    mock_authenticate_user: AsyncMock,
) -> None:
    user = User(
        id=1,
        email="testuser@example.com",
        full_name="Test User",
        disabled=False,
        email_verified=True,
        auth_method=AuthProvider.EMAIL,
        photo=None,
        hashed_password=passwords["hashed_password"],
    )

    now = int(time())
    access_payload = {"sub": user.email, "exp": now + 3600}
    refresh_payload = {
        "sub": user.email,
        "type": "refresh",
        "exp": now + 7200,
    }
    tokens = Token(
        access_token=jwt.encode(access_payload, secret_key, algorithm=algorithm),
        refresh_token=jwt.encode(refresh_payload, secret_key, algorithm=algorithm),
        token_type="bearer",
    )

    expected = {"token": tokens, "user_id": user.id}

    mock_authenticate_user.return_value = user
    mock_create_tokens.return_value = tokens

    actual = await handler.handle_signin(user.email, passwords["password"])

    assert actual == expected
    mock_authenticate_user.assert_awaited_once_with(user.email, passwords["password"])
    mock_create_tokens.assert_called_once_with(user.email)


@patch("dataforce_studio.handlers.auth.jwt.decode")
@patch.object(AuthHandler, "_create_tokens", new_callable=MagicMock)
@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@patch(
    "dataforce_studio.handlers.auth.TokenBlackListRepository.is_token_blacklisted",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.auth.TokenBlackListRepository.add_token",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_handle_refresh_token(
    mock_add_token: AsyncMock,
    mock_is_token_blacklisted: AsyncMock,
    mock_get_user: AsyncMock,
    mock_create_tokens: MagicMock,
    mock_jwt_decode: MagicMock,
) -> None:
    user = User(
        id=1,
        email="testuser@example.com",
        full_name="Test User",
        disabled=False,
        email_verified=True,
        auth_method=AuthProvider.EMAIL,
        photo=None,
        hashed_password=passwords["hashed_password"],
    )

    now = int(time())
    access_payload = {"sub": user.email, "exp": now + 3600}
    refresh_payload = {
        "sub": user.email,
        "type": "refresh",
        "exp": now + 7200,
    }
    tokens = Token(
        access_token=jwt.encode(access_payload, secret_key, algorithm=algorithm),
        refresh_token=jwt.encode(refresh_payload, secret_key, algorithm=algorithm),
        token_type="bearer",
    )

    mock_jwt_decode.return_value = {
        "sub": user.email,
        "type": "refresh",
        "exp": int(time()) + 300,
    }
    mock_is_token_blacklisted.return_value = False
    mock_get_user.return_value = user
    mock_create_tokens.return_value = tokens

    result = await handler.handle_refresh_token(tokens.refresh_token)

    assert result == tokens
    mock_is_token_blacklisted.assert_awaited_once_with(tokens.refresh_token)
    mock_get_user.assert_awaited_once_with(user.email)
    mock_add_token.assert_awaited_once()
    mock_create_tokens.assert_called_once_with(user.email)


@patch("dataforce_studio.handlers.auth.jwt.decode")
@pytest.mark.asyncio
async def test_handle_refresh_token_type_isnt_refresh(
    mock_jwt_decode: MagicMock,
) -> None:
    test_email = "testuser@example.com"

    now = int(time())
    access_payload = {"sub": test_email, "exp": now + 3600}
    refresh_payload = {
        "sub": test_email,
        "type": "refresh",
        "exp": now + 7200,
    }
    tokens = Token(
        access_token=jwt.encode(access_payload, secret_key, algorithm=algorithm),
        refresh_token=jwt.encode(refresh_payload, secret_key, algorithm=algorithm),
        token_type="bearer",
    )

    mock_jwt_decode.return_value = {
        "sub": test_email,
        "type": "bearer",
        "exp": int(time()) + 300,
    }

    with pytest.raises(AuthError, match="Invalid token type") as error:
        await handler.handle_refresh_token(tokens.refresh_token)

    assert error.value.status_code == 400


@patch("dataforce_studio.handlers.auth.jwt.decode")
@pytest.mark.asyncio
async def test_handle_refresh_token_email_is_none(mock_jwt_decode: MagicMock) -> None:
    test_email = "testuser@example.com"

    now = int(time())
    access_payload = {"sub": test_email, "exp": now + 3600}
    refresh_payload = {
        "sub": test_email,
        "type": "refresh",
        "exp": now + 7200,
    }
    tokens = Token(
        access_token=jwt.encode(access_payload, secret_key, algorithm=algorithm),
        refresh_token=jwt.encode(refresh_payload, secret_key, algorithm=algorithm),
        token_type="bearer",
    )

    mock_jwt_decode.return_value = {
        "sub": None,
        "type": "refresh",
        "exp": int(time()) + 300,
    }

    with pytest.raises(AuthError, match="Invalid token") as error:
        await handler.handle_refresh_token(tokens.refresh_token)

    assert error.value.status_code == 400


@patch("dataforce_studio.handlers.auth.jwt.decode")
@patch(
    "dataforce_studio.handlers.auth.TokenBlackListRepository.is_token_blacklisted",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_handle_refresh_token_has_been_revoked(
    mock_is_token_blacklisted: AsyncMock,
    mock_jwt_decode: MagicMock,
) -> None:
    test_email = "testuser@example.com"

    now = int(time())
    access_payload = {"sub": test_email, "exp": now + 3600}
    refresh_payload = {
        "sub": test_email,
        "type": "refresh",
        "exp": now + 7200,
    }
    tokens = Token(
        access_token=jwt.encode(access_payload, secret_key, algorithm=algorithm),
        refresh_token=jwt.encode(refresh_payload, secret_key, algorithm=algorithm),
        token_type="bearer",
    )

    mock_jwt_decode.return_value = {
        "sub": test_email,
        "type": "refresh",
        "exp": int(time()) + 300,
    }
    mock_is_token_blacklisted.return_value = True

    with pytest.raises(AuthError, match="Token has been revoked") as error:
        await handler.handle_refresh_token(tokens.refresh_token)

    assert error.value.status_code == 400
    mock_is_token_blacklisted.assert_awaited_once_with(tokens.refresh_token)


@patch("dataforce_studio.handlers.auth.jwt.decode")
@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@patch(
    "dataforce_studio.handlers.auth.TokenBlackListRepository.is_token_blacklisted",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_handle_refresh_token_user_not_found(
    mock_is_token_blacklisted: AsyncMock,
    mock_get_user: AsyncMock,
    mock_jwt_decode: MagicMock,
) -> None:
    test_email = "testuser@example.com"

    now = int(time())
    access_payload = {"sub": test_email, "exp": now + 3600}
    refresh_payload = {
        "sub": test_email,
        "type": "refresh",
        "exp": now + 7200,
    }
    tokens = Token(
        access_token=jwt.encode(access_payload, secret_key, algorithm=algorithm),
        refresh_token=jwt.encode(refresh_payload, secret_key, algorithm=algorithm),
        token_type="bearer",
    )

    mock_jwt_decode.return_value = {
        "sub": test_email,
        "type": "refresh",
        "exp": int(time()) + 300,
    }
    mock_is_token_blacklisted.return_value = False
    mock_get_user.return_value = None

    with pytest.raises(AuthError, match="User not found") as error:
        await handler.handle_refresh_token(tokens.refresh_token)

    assert error.value.status_code == 404
    mock_is_token_blacklisted.assert_awaited_once_with(tokens.refresh_token)
    mock_get_user.assert_awaited_once_with(test_email)


@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@patch(
    "dataforce_studio.handlers.auth.UserRepository.update_user", new_callable=AsyncMock
)
@pytest.mark.asyncio
async def test_update_user(
    mock_update_user: AsyncMock, mock_get_user: AsyncMock
) -> None:
    email = "test@example.com"
    update_payload = UpdateUserIn(full_name="Updated Name")

    test_user = User(
        id=1,
        email=email,
        full_name="Test User",
        disabled=False,
        email_verified=True,
        auth_method=AuthProvider.EMAIL,
        photo=None,
        hashed_password=passwords["hashed_password"],
    )

    mock_get_user.return_value = test_user
    mock_update_user.return_value = True

    result = await handler.update_user(email, update_payload)

    assert result is True
    mock_get_user.assert_awaited_once_with(email)
    expected_update = UpdateUser(full_name="Updated Name", email=email)
    mock_update_user.assert_awaited_once_with(expected_update)


@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_update_user_not_found(mock_get_user: AsyncMock) -> None:
    email = "test@example.com"
    update_payload = UpdateUserIn(full_name="Updated Name")

    mock_get_user.return_value = None

    with pytest.raises(AuthError, match="User not found") as exc:
        await handler.update_user(email, update_payload)

    assert exc.value.status_code == 404
    mock_get_user.assert_awaited_once_with(email)


@patch(
    "dataforce_studio.handlers.auth.UserRepository.delete_user", new_callable=AsyncMock
)
@pytest.mark.asyncio
async def test_handle_delete_account(mock_delete_user: AsyncMock) -> None:
    email = "test@example.com"

    actual = await handler.handle_delete_account(email)

    assert actual is None
    mock_delete_user.assert_awaited_once_with(email)


@patch(
    "dataforce_studio.handlers.auth.UserRepository.get_public_user",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_handle_get_current_user(mock_get_public_user: AsyncMock) -> None:
    user = UserOut(
        id=1,
        email="testuser@example.com",
        full_name="Test User",
        disabled=False,
        email_verified=True,
        auth_method=AuthProvider.EMAIL,
        photo=None,
    )
    mock_get_public_user.return_value = user

    result = await handler.handle_get_current_user(user.email)

    assert result == user
    mock_get_public_user.assert_awaited_once_with(user.email)


@patch(
    "dataforce_studio.handlers.auth.UserRepository.get_public_user",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_handle_get_current_user_not_found(
    mock_get_public_user: AsyncMock,
) -> None:
    test_email = "testuser@example.com"
    mock_get_public_user.return_value = None

    with pytest.raises(AuthError, match="User not found") as error:
        await handler.handle_get_current_user(test_email)

    assert error.value.status_code == 404
    mock_get_public_user.assert_awaited_once_with(test_email)


@patch(
    "dataforce_studio.handlers.auth.UserRepository.get_public_user",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_handle_get_current_account_is_disabled(
    mock_get_public_user: AsyncMock,
) -> None:
    user = UserOut(
        id=1,
        email="testuser@example.com",
        full_name="Test User",
        disabled=True,
        email_verified=True,
        auth_method=AuthProvider.EMAIL,
        photo=None,
    )

    mock_get_public_user.return_value = user

    with pytest.raises(AuthError, match="Account is disabled") as error:
        await handler.handle_get_current_user(user.email)

    assert error.value.status_code == 400
    mock_get_public_user.assert_awaited_once_with(user.email)


@patch("dataforce_studio.handlers.auth.jwt.decode")
@patch(
    "dataforce_studio.handlers.auth.TokenBlackListRepository.add_token",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_handle_logout(mock_add_token: AsyncMock, mock_jwt_decode: Mock) -> None:
    access_token = "access.token"
    refresh_token = "refresh.token"

    mock_jwt_decode.side_effect = [{"exp": 12345}, {"exp": 67890}]

    await handler.handle_logout(access_token, refresh_token)

    assert mock_jwt_decode.call_count == 2
    mock_add_token.assert_any_await(access_token, 67890)
    mock_add_token.assert_any_await(refresh_token, 67890)
    assert mock_add_token.await_count == 2


@patch("dataforce_studio.handlers.auth.jwt.decode")
@pytest.mark.asyncio
async def test_handle_logout_invalid_refresh_token(mock_jwt_decode: Mock) -> None:
    mock_jwt_decode.side_effect = InvalidTokenError("Invalid refresh")

    with pytest.raises(AuthError, match="Invalid refresh token") as error:
        await handler.handle_logout(None, "token")

    assert error.value.status_code == 400


@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
@patch("httpx.AsyncClient.get", new_callable=AsyncMock)
@patch(
    "dataforce_studio.handlers.auth.AuthHandler._create_tokens", new_callable=MagicMock
)
@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@patch(
    "dataforce_studio.handlers.auth.UserRepository.create_user", new_callable=AsyncMock
)
@patch(
    "dataforce_studio.handlers.auth.UserRepository.update_user", new_callable=AsyncMock
)
@pytest.mark.asyncio
async def test_handle_google_auth(
    mock_update_user: AsyncMock,
    mock_create_user: AsyncMock,
    mock_get_user: AsyncMock,
    mock_create_tokens: MagicMock,
    mock_get: AsyncMock,
    mock_post: AsyncMock,
) -> None:
    user = User(
        id=1,
        email="testuser@example.com",
        full_name="Test User",
        disabled=False,
        email_verified=True,
        auth_method=AuthProvider.EMAIL,
        photo=None,
        hashed_password=passwords["hashed_password"],
    )

    now = int(time())
    access_payload = {"sub": user.email, "exp": now + 3600}
    refresh_payload = {
        "sub": user.email,
        "type": "refresh",
        "exp": now + 7200,
    }
    tokens = Token(
        access_token=jwt.encode(access_payload, secret_key, algorithm=algorithm),
        refresh_token=jwt.encode(refresh_payload, secret_key, algorithm=algorithm),
        token_type="bearer",
    )

    expected = {"token": tokens, "user_id": user.id}

    mock_post.return_value.status_code = 200
    mock_post.return_value.json = MagicMock(
        return_value={"access_token": "fake_access_token"}
    )

    mock_get.return_value.status_code = 200
    mock_get.return_value.json = MagicMock(
        return_value={
            "email": user.email,
            "name": user.full_name,
            "picture": "http://example.com/photo.jpg",
        }
    )

    mock_get_user.return_value = None
    mock_create_user.return_value = user
    mock_create_tokens.return_value = tokens

    result = await handler.handle_google_auth("code")

    assert result == expected
    mock_post.assert_awaited_once()
    mock_get.assert_awaited_once()
    mock_create_user.assert_awaited_once()
    mock_create_tokens.assert_called_once_with(user.email)


@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_google_auth_token_failure(mock_post: AsyncMock) -> None:
    mock_post.return_value.status_code = 400

    with pytest.raises(
        AuthError, match="Failed to retrieve token from Google"
    ) as error:
        await handler.handle_google_auth("code")

    assert error.value.status_code == 400


@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_google_auth_no_access_token(mock_post: AsyncMock) -> None:
    mock_post.return_value.status_code = 200
    mock_post.return_value.json = MagicMock(return_value={})

    with pytest.raises(AuthError, match="Failed to retrieve access token") as error:
        await handler.handle_google_auth("code")
    assert error.value.status_code == 400


@patch("httpx.AsyncClient.get", new_callable=AsyncMock)
@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_google_auth_userinfo_failure(
    mock_post: AsyncMock, mock_get: AsyncMock
) -> None:
    test_access_token = "fake_access_token"

    mock_post.return_value.status_code = 200
    mock_post.return_value.json = MagicMock(
        return_value={"access_token": test_access_token}
    )

    mock_get.return_value.status_code = 400

    with pytest.raises(
        AuthError, match="Failed to retrieve user info from Google"
    ) as error:
        await handler.handle_google_auth("code")
    assert error.value.status_code == 400


@patch("httpx.AsyncClient.get", new_callable=AsyncMock)
@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_google_auth_no_email(mock_post: AsyncMock, mock_get: AsyncMock) -> None:
    test_access_token = "fake_access_token"

    mock_post.return_value.status_code = 200
    mock_post.return_value.json = MagicMock(
        return_value={"access_token": test_access_token}
    )

    mock_get.return_value.status_code = 200
    mock_get.return_value.json = MagicMock(
        return_value={"name": "Test", "picture": "url"}
    )

    with pytest.raises(AuthError, match="Failed to retrieve user email") as error:
        await handler.handle_google_auth("code")

    assert error.value.status_code == 400


@patch("httpx.AsyncClient.get", new_callable=AsyncMock)
@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
@patch(
    "dataforce_studio.handlers.auth.AuthHandler._create_tokens", new_callable=MagicMock
)
@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@patch(
    "dataforce_studio.handlers.auth.UserRepository.update_user", new_callable=AsyncMock
)
@pytest.mark.asyncio
async def test_google_auth_updates_non_google_user(
    mock_update_user: AsyncMock,
    mock_get_user: AsyncMock,
    mock_create_tokens: MagicMock,
    mock_post: AsyncMock,
    mock_get: AsyncMock,
) -> None:
    test_access_token = "fake_access_token"

    now = int(time())
    access_payload = {"sub": "user@example.com", "exp": now + 3600}
    refresh_payload = {
        "sub": "user@example.com",
        "type": "refresh",
        "exp": now + 7200,
    }
    tokens = Token(
        access_token=jwt.encode(access_payload, secret_key, algorithm=algorithm),
        refresh_token=jwt.encode(refresh_payload, secret_key, algorithm=algorithm),
        token_type="bearer",
    )

    mock_post.return_value.status_code = 200
    mock_post.return_value.json = MagicMock(
        return_value={"access_token": test_access_token}
    )

    mock_get.return_value.status_code = 200
    mock_get.return_value.json = MagicMock(
        return_value={
            "email": "user@example.com",
            "name": "Test User",
            "picture": "http://example.com/photo.jpg",
        }
    )

    existing_user = MagicMock(
        email="user@example.com",
        auth_method=AuthProvider.EMAIL,
        photo="http://example.com/photo.jpg",
    )
    mock_get_user.return_value = existing_user
    mock_create_tokens.return_value = tokens

    await handler.handle_google_auth("code")

    mock_update_user.assert_awaited_once_with(
        UpdateUser(email="user@example.com", auth_method=AuthProvider.GOOGLE)
    )


@patch.object(AuthHandler, "_create_token")
def test_generate_password_reset_token(mock_create_token: MagicMock) -> None:
    email = "testuser@example.com"

    mock_create_token.return_value = "test_token"
    actual = handler._generate_password_reset_token(email)

    assert actual == "test_token"
    mock_create_token.assert_called_once_with(
        data={"sub": email, "type": "password_reset"},
        expires_delta=3600,
    )


@patch(
    "dataforce_studio.handlers.auth.EmailHandler.send_password_reset_email",
    new_callable=MagicMock,
)
@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@patch.object(AuthHandler, "_generate_password_reset_token")
@patch.object(AuthHandler, "_get_password_reset_link")
@pytest.mark.asyncio
async def test_send_password_reset_email(
    mock_get_password_reset_link: MagicMock,
    mock_generate_password_reset_token: MagicMock,
    mock_get_user: AsyncMock,
    mock_send_email: MagicMock,
) -> None:
    user = User(
        id=1,
        email="testuser@example.com",
        full_name="Test User",
        disabled=False,
        email_verified=True,
        auth_method=AuthProvider.EMAIL,
        photo=None,
        hashed_password=passwords["hashed_password"],
    )
    token = "token"
    link = f"https://example.com/reset?token=${token}"

    mock_generate_password_reset_token.return_value = token
    mock_get_password_reset_link.return_value = link
    mock_get_user.return_value = user

    await handler.send_password_reset_email(user.email)

    mock_get_user.assert_awaited_once_with(user.email)
    mock_generate_password_reset_token.assert_called_once_with(user.email)
    mock_get_password_reset_link.assert_called_once_with(token)
    mock_send_email.assert_called_once_with(user.email, link, user.full_name)


@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_send_password_reset_email_user_not_found(
    mock_get_user: AsyncMock,
) -> None:
    test_email = "testuser@example.com"
    mock_get_user.return_value = None

    actual = await handler.send_password_reset_email(test_email)

    assert actual is None


@patch("dataforce_studio.handlers.auth.config.CHANGE_PASSWORD_URL", "https://test.com/")
def test_get_password_reset_link() -> None:
    token = "token"
    expected = "https://test.com/" + token

    actual = handler._get_password_reset_link(token)

    assert actual == expected


@patch("dataforce_studio.handlers.auth.jwt.decode")
@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@patch(
    "dataforce_studio.handlers.auth.UserRepository.update_user", new_callable=AsyncMock
)
@pytest.mark.asyncio
async def test_handle_email_confirmation(
    mock_update_user: AsyncMock,
    mock_get_user: AsyncMock,
    mock_jwt_decode: MagicMock,
) -> None:
    user = User(
        id=1,
        email="testuser@example.com",
        full_name="Test User",
        disabled=False,
        email_verified=False,
        auth_method=AuthProvider.EMAIL,
        photo=None,
        hashed_password=passwords["hashed_password"],
    )

    mock_jwt_decode.return_value = {"sub": user.email}
    mock_get_user.return_value = user

    await handler.handle_email_confirmation("token")

    mock_jwt_decode.assert_called_once()
    mock_get_user.assert_awaited_once_with(user.email)
    mock_update_user.assert_awaited_once()


@patch("dataforce_studio.handlers.auth.jwt.decode")
@pytest.mark.asyncio
async def test_handle_email_confirmation_invalid_token(
    mock_jwt_decode: MagicMock,
) -> None:
    mock_jwt_decode.side_effect = InvalidTokenError()

    with pytest.raises(AuthError, match="Invalid token") as error:
        await handler.handle_email_confirmation("token")

    assert error.value.status_code == 400


@patch("dataforce_studio.handlers.auth.jwt.decode")
@pytest.mark.asyncio
async def test_handle_email_confirmation_cant_get_email(
    mock_jwt_decode: MagicMock,
) -> None:
    mock_jwt_decode.return_value = {"sub": None}

    with pytest.raises(AuthError, match="Invalid token") as error:
        await handler.handle_email_confirmation("token")

    assert error.value.status_code == 400


@patch("dataforce_studio.handlers.auth.jwt.decode")
@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_handle_email_confirmation_user_not_found(
    mock_get_user: AsyncMock, mock_jwt_decode: MagicMock
) -> None:
    test_email = "testuser@example.com"
    mock_jwt_decode.return_value = {"sub": test_email}
    mock_get_user.return_value = None

    with pytest.raises(AuthError, match="User not found") as error:
        await handler.handle_email_confirmation("token")

    assert error.value.status_code == 404
    mock_jwt_decode.assert_called_once()
    mock_get_user.assert_awaited_once()


@patch("dataforce_studio.handlers.auth.jwt.decode")
@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_handle_email_confirmation_already_verified(
    mock_get_user: AsyncMock, mock_jwt_decode: MagicMock
) -> None:
    user = User(
        id=1,
        email="testuser@example.com",
        full_name="Test User",
        disabled=False,
        email_verified=True,
        auth_method=AuthProvider.EMAIL,
        photo=None,
        hashed_password=passwords["hashed_password"],
    )

    mock_jwt_decode.return_value = {"sub": user.email}
    mock_get_user.return_value = user

    with pytest.raises(AuthError, match="Email already verified") as error:
        await handler.handle_email_confirmation("token")

    assert error.value.status_code == 400
    mock_jwt_decode.assert_called_once()
    mock_get_user.assert_awaited_once()


@patch("dataforce_studio.handlers.auth.jwt.decode")
@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@patch(
    "dataforce_studio.handlers.auth.UserRepository.update_user", new_callable=AsyncMock
)
@patch("dataforce_studio.handlers.auth.AuthHandler._get_password_hash")
@pytest.mark.asyncio
async def test_handle_reset_password(
    mock_hash: MagicMock,
    mock_update: AsyncMock,
    mock_get_user: AsyncMock,
    mock_jwt_decode: MagicMock,
) -> None:
    user = User(
        id=1,
        email="testuser@example.com",
        full_name="Test User",
        disabled=False,
        email_verified=True,
        auth_method=AuthProvider.EMAIL,
        photo=None,
        hashed_password=passwords["hashed_password"],
    )
    new_password = "new_pass"
    update_user = UpdateUser(email=user.email, hashed_password=user.hashed_password)
    mock_jwt_decode.return_value = {"sub": user.email, "exp": int(time()) + 3600}
    mock_get_user.return_value = user
    mock_hash.return_value = user.hashed_password

    await handler.handle_reset_password("token", new_password)

    mock_jwt_decode.assert_called_once()
    mock_get_user.assert_awaited_once_with(user.email)
    mock_hash.assert_called_once_with(new_password)
    mock_update.assert_awaited_once_with(update_user)


@patch("dataforce_studio.handlers.auth.jwt.decode")
@pytest.mark.asyncio
async def test_handle_reset_expired(mock_jwt_decode: MagicMock) -> None:
    test_email = "testuser@example.com"
    new_password = "new_pass"
    mock_jwt_decode.return_value = {"sub": test_email, "exp": None}

    with pytest.raises(AuthError, match="Token expired") as error:
        await handler.handle_reset_password("token", new_password)

    assert error.value.status_code == 400
    mock_jwt_decode.assert_called_once()


@patch("dataforce_studio.handlers.auth.jwt.decode")
@pytest.mark.asyncio
async def test_handle_reset_password_cant_get_email(mock_jwt_decode: MagicMock) -> None:
    new_password = "new_pass"
    mock_jwt_decode.return_value = {"sub": None, "exp": int(time()) + 3600}

    with pytest.raises(AuthError, match="Invalid token") as error:
        await handler.handle_reset_password("token", new_password)

    assert error.value.status_code == 400
    mock_jwt_decode.assert_called_once()


@patch("dataforce_studio.handlers.auth.jwt.decode")
@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_handle_reset_password_user_not_found(
    mock_get_user: AsyncMock, mock_jwt_decode: MagicMock
) -> None:
    test_email = "testuser@example.com"
    new_password = "new_pass"
    mock_jwt_decode.return_value = {"sub": test_email, "exp": int(time()) + 3600}
    mock_get_user.return_value = None

    with pytest.raises(AuthError, match="User not found") as error:
        await handler.handle_reset_password("token", new_password)

    assert error.value.status_code == 404
    mock_jwt_decode.assert_called_once()
    mock_get_user.assert_awaited_once_with(test_email)


@patch("dataforce_studio.handlers.auth.jwt.decode")
@pytest.mark.asyncio
async def test_handle_reset_password_invalid_token(mock_jwt_decode: MagicMock) -> None:
    mock_jwt_decode.side_effect = InvalidTokenError()

    with pytest.raises(AuthError, match="Invalid token") as exc:
        await handler.handle_reset_password("token", "new_pass")

    assert exc.value.status_code == 400
    mock_jwt_decode.assert_called_once()


@patch(
    "dataforce_studio.handlers.auth.TokenBlackListRepository.is_token_blacklisted",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_is_token_blacklisted(mock_is_token_blacklisted: AsyncMock) -> None:
    mock_is_token_blacklisted.return_value = True

    token = "token"

    result = await handler.is_token_blacklisted(token)

    assert result is True
    mock_is_token_blacklisted.assert_awaited_once_with(token)
