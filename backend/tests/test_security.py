"""Tests for password hashing and JWT helpers."""
import pytest

from app.core.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.utils.exceptions import InvalidCredentialsError


def test_password_round_trip():
    hashed = hash_password("Secret!123")
    assert verify_password("Secret!123", hashed)
    assert not verify_password("wrong", hashed)


def test_jwt_round_trip():
    token = create_access_token("user-123", extra_claims={"role": "ADMIN"})
    payload = decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["role"] == "ADMIN"
    assert payload["type"] == "access"


def test_jwt_rejects_tampered_token():
    token = create_access_token("user-123") + "tamper"
    with pytest.raises(InvalidCredentialsError):
        decode_token(token)
