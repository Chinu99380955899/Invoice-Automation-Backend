"""Authentication endpoints."""
from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DBSession
from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.schemas.user import Token, UserCreate, UserLogin, UserRead
from app.services.user_service import UserService
from app.utils.exceptions import InvalidCredentialsError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def register(data: UserCreate, db: DBSession) -> UserRead:
    user = UserService(db).create(data)
    return UserRead.model_validate(user)


@router.post("/login", response_model=Token)
def login(data: UserLogin, db: DBSession) -> Token:
    user = UserService(db).authenticate(data.email, data.password)
    return Token(
        access_token=create_access_token(
            subject=str(user.id),
            extra_claims={"role": user.role.value, "email": user.email},
        ),
        refresh_token=create_refresh_token(subject=str(user.id)),
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=Token)
def refresh(refresh_token: str, db: DBSession) -> Token:
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise InvalidCredentialsError("Invalid refresh token")
    user = UserService(db).get_by_id(payload["sub"])
    return Token(
        access_token=create_access_token(
            subject=str(user.id),
            extra_claims={"role": user.role.value, "email": user.email},
        ),
        refresh_token=create_refresh_token(subject=str(user.id)),
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)
