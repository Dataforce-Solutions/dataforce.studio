from fastapi import HTTPException, Request, status
from starlette.authentication import UnauthenticatedUser

from dataforce_studio.models.auth import AuthUser


def get_current_user(request: Request) -> AuthUser:
    if isinstance(request.user, UnauthenticatedUser):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    return request.user
