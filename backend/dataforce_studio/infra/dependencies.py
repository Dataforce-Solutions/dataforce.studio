from fastapi import HTTPException, Request, status
from starlette.authentication import UnauthenticatedUser

from dataforce_studio.models.auth import AuthUser
from dataforce_studio.models.errors import AuthError


def get_current_user(request: Request) -> AuthUser:
    if isinstance(request.user, UnauthenticatedUser):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    try:
        return request.user
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e
