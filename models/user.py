"""SQLAlchemy models describing users, profiles, usage metrics, and transcripts."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import List, Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    """Primary account holder with credential metadata."""

    __tablename__ = "users"
    __allow_unmapped__ = True

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    profiles: List["Profile"] = relationship("Profile", back_populates="owner", cascade="all, delete-orphan")
    usage_meters: List["UsageMeter"] = relationship(
        "UsageMeter", back_populates="user", cascade="all, delete-orphan"
    )
    transcripts: List["Transcript"] = relationship(
        "Transcript", back_populates="user", cascade="all, delete-orphan"
    )


class Profile(Base):
    """Profile scoped within a user account, enabling multi-voice/purpose usage."""

    __tablename__ = "profiles"
    __allow_unmapped__ = True

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    owner: User = relationship("User", back_populates="profiles")
    usage_meters: List["UsageMeter"] = relationship(
        "UsageMeter", back_populates="profile", cascade="all, delete-orphan"
    )
    transcripts: List["Transcript"] = relationship(
        "Transcript", back_populates="profile", cascade="all, delete-orphan"
    )


class UsageMeter(Base):
    """Tracks per-user and per-profile resource consumption for dashboards."""

    __tablename__ = "usage_meters"
    __allow_unmapped__ = True

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    profile_id = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True, index=True)
    month = Column(String(7), nullable=False, index=True)
    transcription_seconds = Column(Numeric(scale=2), default=0)
    transcription_cost = Column(Numeric(scale=4), default=0)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    user: User = relationship("User", back_populates="usage_meters")
    profile: Profile = relationship("Profile", back_populates="usage_meters")


class Transcript(Base):
    """Stores metadata for each transcription job for library management."""

    __tablename__ = "transcripts"
    __allow_unmapped__ = True

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    profile_id = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True, index=True)
    job_id = Column(String(64), unique=True, nullable=False, index=True)
    audio_key = Column(String(512), nullable=False)
    transcript_key = Column(String(512), nullable=True)
    status = Column(String(32), nullable=False, default="queued")
    language = Column(String(32), nullable=True)
    quality_profile = Column(String(32), nullable=True)
    title = Column(String(255), nullable=True)
    tags = Column(String(255), nullable=True)
    segments = Column(Text, nullable=True)
    duration_seconds = Column(Numeric(scale=2), nullable=True)
    error_message = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    completed_at = Column(DateTime, nullable=True)

    user: User = relationship("User", back_populates="transcripts")
    profile: Optional[Profile] = relationship("Profile", back_populates="transcripts")


__all__ = ["Base", "User", "Profile", "UsageMeter", "Transcript"]
