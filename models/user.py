"""SQLAlchemy models describing users, profiles, and usage metrics."""
from __future__ import annotations

from datetime import datetime
from typing import List

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    """Primary account holder with credential metadata."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    profiles: List["Profile"] = relationship("Profile", back_populates="owner", cascade="all, delete-orphan")
    usage_meters: List["UsageMeter"] = relationship(
        "UsageMeter", back_populates="user", cascade="all, delete-orphan"
    )


class Profile(Base):
    """Profile scoped within a user account, enabling multi-voice/purpose usage."""

    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    owner: User = relationship("User", back_populates="profiles")
    usage_meters: List["UsageMeter"] = relationship(
        "UsageMeter", back_populates="profile", cascade="all, delete-orphan"
    )


class UsageMeter(Base):
    """Tracks per-user and per-profile resource consumption for dashboards."""

    __tablename__ = "usage_meters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    profile_id = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True, index=True)
    month = Column(String(7), nullable=False, index=True)
    transcription_seconds = Column(Numeric(scale=2), default=0)
    transcription_cost = Column(Numeric(scale=4), default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: User = relationship("User", back_populates="usage_meters")
    profile: Profile = relationship("Profile", back_populates="usage_meters")
