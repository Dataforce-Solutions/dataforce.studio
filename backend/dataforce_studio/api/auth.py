from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import FastAPI, HTTPException, Request, status, Form, Depends
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from starlette.authentication import AuthCredentials, AuthenticationBackend, BaseUser
from starlette.middleware.authentication import AuthenticationMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware

SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 180
REFRESH_TOKEN_EXPIRE_DAYS = 7

fake_users_db = {}
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

token_blacklist: dict[str, datetime] = {}


def is_token_blacklisted(token: str) -> bool:
    return token in token_blacklist


def blacklist_token(token: str, expires: datetime):
    token_blacklist[token] = expires


class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: str | None = None


class User(BaseModel):
    email: EmailStr
    full_name: str | None = None
    disabled: bool | None = None


class UserInDB(User):
    hashed_password: str


class AuthUser(BaseUser):
    def __init__(
        self,
        email: str,
        full_name: str | None = None,
        disabled: bool | None = None,
    ):
        self.email = email
        self.full_name = full_name
        self.disabled = disabled

    @property
    def is_authenticated(self):
        return True

    @property
    def display_name(self):
        return self.email


class JWTAuthenticationBackend(AuthenticationBackend):
    async def authenticate(self, conn):
        authorization: str = conn.headers.get("Authorization")
        if not authorization:
            return None

        try:
            scheme, token = authorization.split()
            if scheme.lower() != "bearer":
                return None

            if is_token_blacklisted(token):
                return None

            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            email: str = payload.get("sub")
            if email is None:
                return None

            user_in_db = get_user(fake_users_db, email=email)
            if not user_in_db:
                return None

            user = AuthUser(
                email=user_in_db.email,
                full_name=user_in_db.full_name,
                disabled=user_in_db.disabled,
            )
            return AuthCredentials(["authenticated"]), user
        except (InvalidTokenError, ValueError):
            return None


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def get_user(db, email: str):
    if email in db:
        user_dict = db[email]
        return UserInDB(**user_dict)


def authenticate_user(fake_db, email: str, password: str):
    user = get_user(fake_db, email)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


def create_token(data: dict, expires_delta: timedelta):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(AuthenticationMiddleware, backend=JWTAuthenticationBackend())
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/signin", scheme_name="JWT")


@app.post("/auth/signup", response_model=Token)
async def signup(
    email: Annotated[EmailStr, Form()],
    password: Annotated[str, Form()],
    full_name: Annotated[str | None, Form()] = None,
):
    if fake_users_db.get(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    if not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is required",
        )

    hashed_password = get_password_hash(password)
    user = UserInDB(
        email=email,
        full_name=full_name,
        disabled=False,
        hashed_password=hashed_password,
    )
    fake_users_db[email] = user.model_dump()

    access_token = create_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = create_token(
        data={"sub": user.email, "type": "refresh"},
        expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )

    return Token(
        access_token=access_token, refresh_token=refresh_token, token_type="bearer"
    )


@app.post("/auth/signin", response_model=Token)
async def signin(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],  # Now it should work
):
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = create_token(
        data={"sub": user.email, "type": "refresh"},
        expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )

    return Token(
        access_token=access_token, refresh_token=refresh_token, token_type="bearer"
    )


class RefreshRequest(BaseModel):
    refresh_token: str


@app.post("/auth/refresh", response_model=Token)
async def refresh_token(refresh_request: RefreshRequest):
    try:
        # Decode the refresh token
        payload = jwt.decode(
            refresh_request.refresh_token, SECRET_KEY, algorithms=[ALGORITHM]
        )

        # Verify it's a refresh token
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token type"
            )

        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token"
            )

        # Check if token is blacklisted
        if is_token_blacklisted(refresh_request.refresh_token):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Token has been revoked"
            )

        # Verify user still exists
        user = get_user(fake_users_db, email)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Blacklist the used refresh token
        token_expiry = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        blacklist_token(refresh_request.refresh_token, token_expiry)

        # Create new tokens
        access_token = create_token(
            data={"sub": email},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        )

        new_refresh_token = create_token(
            data={"sub": email, "type": "refresh"},
            expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        )

        return Token(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
        )

    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid refresh token"
        )


@app.post("/auth/change-password")
async def change_password(
    request: Request,
    current_password: Annotated[str, Form()],
    new_password: Annotated[str, Form()],
    _: str = Depends(oauth2_scheme),
):
    if not request.user.is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    user = get_user(fake_users_db, request.user.email)
    if not verify_password(current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid current password"
        )

    fake_users_db[user.email]["hashed_password"] = get_password_hash(new_password)
    return {"detail": "Password changed successfully"}


@app.delete("/auth/delete-account")
async def delete_account(request: Request, _: str = Depends(oauth2_scheme)):
    if not request.user.is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    email = request.user.email
    if email in fake_users_db:
        del fake_users_db[email]
        return {"detail": "Account deleted successfully"}

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


@app.get("/auth/me", response_model=User)
async def get_current_user(request: Request, _: str = Depends(oauth2_scheme)):
    if not request.user.is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    user_in_db = get_user(fake_users_db, email=request.user.email)
    if user_in_db is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if user_in_db.disabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Account is disabled"
        )

    return User(
        email=user_in_db.email,
        full_name=user_in_db.full_name,
        disabled=user_in_db.disabled,
    )


@app.post("/auth/logout")
async def logout(
    request: Request,
    refresh_token: Annotated[str, Form()],
    _: str = Depends(oauth2_scheme),
):
    if not request.user.is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    try:
        # Decode the refresh token
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        token_expiry = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)

        # Blacklist both the access token and refresh token
        auth_header = request.headers.get("Authorization")
        if auth_header:
            access_token = auth_header.split()[1]
            access_payload = jwt.decode(
                access_token, SECRET_KEY, algorithms=[ALGORITHM]
            )
            access_expiry = datetime.fromtimestamp(
                access_payload["exp"], tz=timezone.utc
            )
            blacklist_token(access_token, access_expiry)

        blacklist_token(refresh_token, token_expiry)
        return {"detail": "Successfully logged out"}

    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid refresh token"
        )

