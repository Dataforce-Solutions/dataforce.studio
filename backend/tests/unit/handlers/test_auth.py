from unittest.mock import Mock, patch

from dataforce_studio.handlers.auth import AuthHandler
from passlib.context import CryptContext

handler = AuthHandler(
    secret_key="test",
    algorithm="HS256",
    pwd_context=CryptContext(schemes=["bcrypt"], deprecated="auto"),
)


@patch("passlib.context.CryptContext.hash")
def test_get_password_hash(patched_hash: Mock) -> None:
    password = "test_password"
    hashed_password = "$2b$12$rr/FMTnWz0BGDTiG//l.YuzZe9ZIpZTPZD5FeAVDDdqgchIDUyD66"
    patched_hash.return_value = hashed_password

    hashed_password_from_auth_handler = handler._get_password_hash(password)
    assert hashed_password == hashed_password_from_auth_handler
