"""Schema definitions with optional Pydantic support."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

try:  # pragma: no cover - optional dependency
    from pydantic import BaseModel, EmailStr
    try:  # pragma: no cover - optional dependency
        import email_validator  # type: ignore
    except ImportError:  # pragma: no cover
        EmailStr = str  # type: ignore
except ImportError:  # pragma: no cover
    EmailStr = str  # type: ignore

    class BaseModel:  # type: ignore
        def __init__(self, **data):
            for name, annotation in self.__annotations__.items():  # type: ignore[attr-defined]
                default = getattr(self.__class__, name, None)
                value = data.get(name, default)
                if callable(value):
                    value = value()
                setattr(self, name, value)

        def dict(self):  # pragma: no cover - helper for testing
            return {name: getattr(self, name) for name in self.__annotations__}  # type: ignore[attr-defined]

        @classmethod
        def from_orm(cls, obj):  # pragma: no cover - minimal implementation
            data = {}
            for name in cls.__annotations__:  # type: ignore[attr-defined]
                data[name] = getattr(obj, name, None)
            return cls(**data)


class ProfileCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ProfileRead(ProfileCreate):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


class UsageMeterRead(BaseModel):
    id: int
    month: str
    transcription_seconds: float
    transcription_cost: float
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserRead(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    created_at: datetime
    profiles: List[ProfileRead] = []

    class Config:
        orm_mode = True

    def __init__(self, **data):
        profiles = data.pop("profiles", None)
        profiles_list = list(profiles) if profiles is not None else []
        super().__init__(profiles=profiles_list, **data)


class TranscriptResponse(BaseModel):
    job_id: str
    status: str
