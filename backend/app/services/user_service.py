"""User & authentication service."""
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.db.models.user import User, UserRole
from app.schemas.user import UserCreate
from app.utils.exceptions import ConflictError, InvalidCredentialsError, NotFoundError


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.scalar(select(User).where(User.email == email.lower()))

    def get_by_id(self, user_id: UUID) -> User:
        user = self.db.get(User, user_id)
        if not user:
            raise NotFoundError("User not found")
        return user

    def create(self, data: UserCreate) -> User:
        if self.get_by_email(data.email):
            raise ConflictError("A user with this email already exists")
        user = User(
            email=data.email.lower(),
            full_name=data.full_name,
            hashed_password=hash_password(data.password),
            role=data.role,
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def authenticate(self, email: str, password: str) -> User:
        user = self.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError("Incorrect email or password")
        if not user.is_active:
            raise InvalidCredentialsError("This account is inactive")
        return user

    def ensure_seed_admin(self) -> User:
        """Idempotently create a default admin for dev/demo."""
        existing = self.get_by_email("admin@invoice.local")
        if existing:
            return existing
        return self.create(
            UserCreate(
                email="admin@invoice.local",
                full_name="System Administrator",
                password="Admin@12345",
                role=UserRole.ADMIN,
            )
        )
