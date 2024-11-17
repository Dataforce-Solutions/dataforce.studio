from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import FastAPI, HTTPException, Request, status, Form, Depends
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
from pydantic import BaseModel
from starlette.authentication import AuthCredentials, AuthenticationBackend, BaseUser
from starlette.middleware.authentication import AuthenticationMiddleware
from fastapi.security import OAuth2PasswordBearer


SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 180

fake_users_db = {}

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)


def authenticate_user(fake_db, username: str, password: str):
    user = get_user(fake_db, username)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


class Token(BaseModel):
    access_token: str
    token_type: str


class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None


class UserInDB(User):
    hashed_password: str


class AuthUser(BaseUser):
    def __init__(
        self,
        username: str,
        email: str | None = None,
        full_name: str | None = None,
        disabled: bool | None = None,
    ):
        self.username = username
        self.email = email
        self.full_name = full_name
        self.disabled = disabled

    @property
    def is_authenticated(self):
        return True

    @property
    def display_name(self):
        return self.username


class JWTAuthenticationBackend(AuthenticationBackend):
    async def authenticate(self, conn):
        authorization: str = conn.headers.get("Authorization")
        if not authorization:
            return None

        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer":
            return None

        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                return None
            user_in_db = get_user(fake_users_db, username=username)
            if not user_in_db:
                return None
            user = AuthUser(
                username=user_in_db.username,
                email=user_in_db.email,
                full_name=user_in_db.full_name,
                disabled=user_in_db.disabled,
            )
            return AuthCredentials(["authenticated"]), user
        except InvalidTokenError:
            return None


app = FastAPI()
app.add_middleware(AuthenticationMiddleware, backend=JWTAuthenticationBackend())


@app.post("/signup")
async def signup(
    request: Request,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
):
    if fake_users_db.get(username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )
    if username and password:
        hashed_password = get_password_hash(password)
        user = UserInDB(
            username=username,
            email=None,
            full_name=None,
            disabled=False,
            hashed_password=hashed_password,
        )
        fake_users_db[username] = user.model_dump()

        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )
        print(fake_users_db)
        return Token(access_token=access_token, token_type="bearer")
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password are required",
        )


@app.post("/signin")
async def signin(
    request: Request,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
):
    print(fake_users_db)
    user = authenticate_user(fake_users_db, username, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/signin")


@app.delete("/delete_user")
async def delete_user(request: Request, _: str = Depends(oauth2_scheme)):
    if not request.user.is_authenticated:
        raise HTTPException(status_code=401, detail="Not authenticated")

    username = request.user.username

    if username in fake_users_db:
        del fake_users_db[username]
        return {"detail": "User deleted"}
    else:
        raise HTTPException(status_code=404, detail="User not found")


@app.get("/users/me", response_model=User)
async def read_users_me(request: Request, _: str = Depends(oauth2_scheme)):
    print(request.user)
    if not request.user.is_authenticated:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_in_db = get_user(fake_users_db, username=request.user.username)
    if user_in_db is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user_in_db.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return User(
        username=user_in_db.username,
        email=user_in_db.email,
        full_name=user_in_db.full_name,
        disabled=user_in_db.disabled,
    )


@app.get("/users/me/items/")
async def read_own_items(request: Request, _: str = Depends(oauth2_scheme)):
    if not request.user.is_authenticated:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return [{"item_id": "Foo", "owner": request.user.username}]
