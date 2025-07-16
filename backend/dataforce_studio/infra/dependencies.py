from fastapi import HTTPException, Request, status


def is_user_authenticated(request: Request) -> None:
    if not request.user.is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    if "jwt" not in request.auth.scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires JWT authentication.",
        )


def is_user_authenticated_jwt_api_key(request: Request) -> None:
    if not request.user.is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
