"""Authentication utilities with minimal dependencies."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, List, Optional

try:  # pragma: no cover - optional dependency
    from fastapi import Depends, HTTPException, status
    from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
except ImportError:  # pragma: no cover
    def Depends(dependency=None):  # type: ignore
        return None

    class HTTPException(Exception):  # type: ignore
        def __init__(self, status_code: int, detail: str, headers: Optional[dict] = None) -> None:
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail
            self.headers = headers or {}

    class _Status:  # type: ignore
        HTTP_401_UNAUTHORIZED = 401

    status = _Status()

    class OAuth2PasswordBearer:  # type: ignore
        def __init__(self, *args, **kwargs) -> None:
            self._message = "FastAPI is required for OAuth2PasswordBearer"

        def __call__(self, *args, **kwargs):  # pragma: no cover
            raise RuntimeError(self._message)

    class OAuth2PasswordRequestForm:  # type: ignore
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError("FastAPI is required for OAuth2PasswordRequestForm")

try:  # pragma: no cover - optional dependency
    from sqlalchemy.orm import Session
except ImportError:  # pragma: no cover
    from typing import Any as Session  # type: ignore

from app.config import get_settings
from app.database import session_scope
from app.utils.jwt import decode_jwt, encode_jwt

try:  # pragma: no cover - optional dependency
    from models.user import Profile, User
except ImportError:  # pragma: no cover
    class Profile:  # type: ignore
        id: int
        name: str
        description: Optional[str]

    class User:  # type: ignore
        id: int
        email: str
        hashed_password: str
        profiles: list

oauth2_scheme = None
try:  # pragma: no cover - optional dependency
    oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")
except RuntimeError:  # pragma: no cover - FastAPI not available
    oauth2_scheme = None


class TokenData:
    def __init__(self, user_id: int):
        self.user_id = user_id


@dataclass
class AuthenticatedProfile:
    id: int
    name: str
    description: Optional[str] = None


@dataclass
class AuthenticatedUser:
    id: int
    email: str
    profiles: List[AuthenticatedProfile] = field(default_factory=list)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        salt_b64, digest_b64 = hashed_password.split(":", 1)
    except ValueError:
        return False
    salt = base64.b64decode(salt_b64.encode("utf-8"))
    expected = base64.b64decode(digest_b64.encode("utf-8"))
    computed = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, 390000)
    return hmac.compare_digest(expected, computed)


def get_password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 390000)
    return f"{base64.b64encode(salt).decode('utf-8')}:{base64.b64encode(digest).decode('utf-8')}"


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=settings.jwt_expiration_minutes))
    to_encode.update({"exp": int(expire.timestamp())})
    return encode_jwt(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def authenticate_user(session: Session, email: str, password: str) -> Optional[User]:
    user = session.query(User).filter(User.email == email).one_or_none()
    if user and verify_password(password, user.hashed_password):
        return user
    return None


def get_current_user(token: str = Depends(oauth2_scheme)) -> AuthenticatedUser:  # type: ignore[call-arg]
    if oauth2_scheme is None:  # pragma: no cover - FastAPI not available
        raise RuntimeError("FastAPI must be installed to use get_current_user")

    settings = get_settings()
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_jwt(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id = int(payload.get("sub"))
    except (ValueError, TypeError, json.JSONDecodeError):
        raise credentials_exception

    with session_scope() as session:
        user = session.query(User).filter(User.id == user_id).one_or_none()
        if user is None:
            raise credentials_exception

        profiles: List[AuthenticatedProfile] = []
        for profile in list(getattr(user, "profiles", []) or []):
            profiles.append(
                AuthenticatedProfile(
                    id=getattr(profile, "id", 0),
                    name=getattr(profile, "name", ""),
                    description=getattr(profile, "description", None),
                )
            )

        return AuthenticatedUser(id=user.id, email=user.email, profiles=profiles)


def login(form_data: OAuth2PasswordRequestForm = Depends()) -> dict:  # type: ignore[call-arg]
    if oauth2_scheme is None:  # pragma: no cover - FastAPI not available
        raise RuntimeError("FastAPI must be installed to use login")

    with session_scope() as session:
        user = authenticate_user(session, form_data.username, form_data.password)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect credentials")
        access_token = create_access_token({"sub": str(user.id)})
        return {"access_token": access_token, "token_type": "bearer"}
