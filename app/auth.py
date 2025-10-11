"""Authentication utilities and FastAPI dependencies."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import session_scope
from models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


class TokenData:
    def __init__(self, user_id: int):
        self.user_id = user_id


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.jwt_expiration_minutes))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def authenticate_user(session: Session, email: str, password: str) -> Optional[User]:
    user = session.query(User).filter(User.email == email).one_or_none()
    if user and verify_password(password, user.hashed_password):
        return user
    return None


def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    settings = get_settings()
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_id: int = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        raise credentials_exception

    with session_scope() as session:
        user = session.query(User).filter(User.id == user_id).one_or_none()
        if user is None:
            raise credentials_exception
        return user


def login(form_data: OAuth2PasswordRequestForm = Depends()) -> dict:
    with session_scope() as session:
        user = authenticate_user(session, form_data.username, form_data.password)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect credentials")
        access_token = create_access_token({"sub": str(user.id)})
        return {"access_token": access_token, "token_type": "bearer"}
