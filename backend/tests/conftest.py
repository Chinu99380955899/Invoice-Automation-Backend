"""Shared pytest fixtures."""
import os
import sys
from pathlib import Path

# Make `app` importable when running from /backend
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Force test-mode config BEFORE importing the app
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-12345678")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("USE_MOCK_AZURE_OCR", "true")
os.environ.setdefault("USE_MOCK_PADDLE_OCR", "true")
os.environ.setdefault("USE_MOCK_INTEGRATIONS", "true")
os.environ.setdefault("LOG_FORMAT", "console")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine("sqlite:///./test.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(test_engine):
    Session = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
