from __future__ import annotations

from datetime import timedelta

from app import auth
from app.config import get_settings
from app.utils.jwt import decode_jwt


def test_password_hash_roundtrip():
    hashed = auth.get_password_hash("secret")
    assert auth.verify_password("secret", hashed)


def test_create_access_token_contains_subject():
    token = auth.create_access_token({"sub": "123"}, expires_delta=timedelta(minutes=5))
    # Ensure token decodes back
    settings = get_settings()
    payload = decode_jwt(
        token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
    )
    assert payload["sub"] == "123"
