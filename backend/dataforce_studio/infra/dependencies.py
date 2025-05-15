from fastapi import HTTPException, Request, status


def is_user_authenticated(request: Request) -> None:
    if not request.user.is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
