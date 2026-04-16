"""Shared FastAPI dependencies."""
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.services.user_service import UserService
from app.utils.exceptions import ForbiddenError, InvalidCredentialsError

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if creds is None or not creds.credentials:
        raise InvalidCredentialsError("Missing authentication token")
    payload = decode_token(creds.credentials)
    if payload.get("type") != "access":
        raise InvalidCredentialsError("Invalid token type")
    try:
        user_id = UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise InvalidCredentialsError("Invalid token subject") from exc
    user = UserService(db).get_by_id(user_id)
    if not user.is_active:
        raise InvalidCredentialsError("User is inactive")
    # Expose on request.state so log middleware can bind user_id
    request.state.user_id = str(user.id)
    return user


def require_role(*roles: UserRole):
    """Dependency factory enforcing that the current user has one of the roles."""
    allowed = set(roles)

    def _checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in allowed:
            raise ForbiddenError(
                f"Requires one of roles: {', '.join(r.value for r in allowed)}"
            )
        return user

    return _checker


CurrentUser = Annotated[User, Depends(get_current_user)]
DBSession = Annotated[Session, Depends(get_db)]
