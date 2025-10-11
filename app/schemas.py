"""Pydantic models used by the FastAPI endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr


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


class TranscriptResponse(BaseModel):
    job_id: str
    status: str
