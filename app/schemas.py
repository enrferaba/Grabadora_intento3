"""Schema definitions with optional Pydantic support."""
from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, TypeAlias

from .models import TranscriptionStatus

try:  # pragma: no cover - optional dependency
    from pydantic import BaseModel, EmailStr, Field
    try:  # pragma: no cover - optional dependency
        from pydantic import ConfigDict  # type: ignore[attr-defined]
    except ImportError:  # pragma: no cover - Pydantic v1
        ConfigDict = dict  # type: ignore[type-arg]
    from pydantic import ValidationError
    from pydantic import __version__ as _pydantic_version

    _IS_PYDANTIC_V1 = _pydantic_version.startswith("1.")
    _HAVE_PYDANTIC = True

    if _IS_PYDANTIC_V1:
        BaseModel.model_dump = BaseModel.dict  # type: ignore[attr-defined]

        @classmethod
        def _compat_model_validate(cls, obj):  # type: ignore[override]
            if isinstance(obj, cls):
                return obj
            try:
                return cls.parse_obj(obj)
            except (TypeError, ValidationError):
                return cls.from_orm(obj)

        BaseModel.model_validate = _compat_model_validate  # type: ignore[attr-defined]

    try:  # pragma: no cover - optional dependency
        import email_validator  # type: ignore
    except ImportError:  # pragma: no cover
        EmailStr = str  # type: ignore
except ImportError:  # pragma: no cover
    EmailStr = str  # type: ignore
    _HAVE_PYDANTIC = False
    _IS_PYDANTIC_V1 = False

    class ConfigDict(dict):  # type: ignore[type-arg]
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

    def Field(*_, default=None, default_factory=None, **__):  # type: ignore
        if default_factory is not None:
            return default_factory()
        return default

    class BaseModel:  # type: ignore
        def __init__(self, **data):
            for name in getattr(self, "__annotations__", {}):
                default = getattr(self.__class__, name, None)
                value = data.get(name, default)
                if callable(value):
                    value = value()
                setattr(self, name, value)

        def dict(self) -> dict:  # pragma: no cover - helper for testing
            return {name: getattr(self, name) for name in getattr(self, "__annotations__", {})}

        def model_dump(self) -> dict:  # pragma: no cover - compatibility helper
            return self.dict()

        def model_dump(self) -> dict:  # pragma: no cover - compatibility helper
            return self.dict()

        @classmethod
        def from_orm(cls, obj):  # pragma: no cover - minimal implementation
            data = {}
            for name in getattr(cls, "__annotations__", {}):
                data[name] = getattr(obj, name, None)
            return cls(**data)

        @classmethod
        def model_validate(cls, obj):  # pragma: no cover - compatibility helper
            if isinstance(obj, cls):
                return obj
            if isinstance(obj, dict):
                return cls(**obj)
            return cls.from_orm(obj)

EmailStrType: TypeAlias = EmailStr  # type: ignore[misc]


def _enable_from_attributes(cls):
    if not _HAVE_PYDANTIC:
        return cls
    if _IS_PYDANTIC_V1:
        config = getattr(cls, "Config", type("Config", (), {}))
        setattr(config, "orm_mode", True)
        cls.Config = config  # type: ignore[attr-defined]
    else:
        existing = getattr(cls, "model_config", ConfigDict())
        merged = {**dict(existing), "from_attributes": True}
        cls.model_config = ConfigDict(**merged)
    return cls


class ProfileCreate(BaseModel):
    name: str
    description: Optional[str] = None


@_enable_from_attributes
class ProfileRead(ProfileCreate):
    id: int
    created_at: datetime


@_enable_from_attributes
class UsageMeterRead(BaseModel):
    id: int
    month: str
    transcription_seconds: float
    transcription_cost: float
    updated_at: Optional[datetime]


class UserCreate(BaseModel):
    email: EmailStrType
    password: str


@_enable_from_attributes
class UserRead(BaseModel):
    id: int
    email: EmailStrType
    is_active: bool
    created_at: datetime
    profiles: List[ProfileRead] = Field(default_factory=list)

    def __init__(self, **data):
        profiles = data.pop("profiles", None)
        profiles_list = list(profiles) if profiles is not None else []
        super().__init__(profiles=profiles_list, **data)


class TranscriptResponse(BaseModel):
    job_id: str
    status: str
    quality_profile: Optional[str] = None


@_enable_from_attributes
class DebugEvent(BaseModel):
    timestamp: str
    stage: str
    level: str
    message: str
    extra: Dict[str, Any] = Field(default_factory=dict)


@_enable_from_attributes
class TranscriptSummary(BaseModel):
    id: int
    job_id: Optional[str] = None
    status: TranscriptionStatus | str
    title: Optional[str] = None
    language: Optional[str] = None
    quality_profile: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    runtime_seconds: Optional[float] = None
    model_size: Optional[str] = None
    device_preference: Optional[str] = None
    beam_size: Optional[int] = None
    subject: Optional[str] = None
    output_folder: Optional[str] = None
    premium_enabled: Optional[bool] = None
    premium_notes: Optional[str] = None
    premium_perks: Optional[List[str]] = None
    error_message: Optional[str] = None
    debug_events: List[DebugEvent] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


@_enable_from_attributes
class TranscriptDetail(TranscriptSummary):
    original_filename: Optional[str] = None
    stored_path: Optional[str] = None
    audio_key: Optional[str] = None
    transcript_key: Optional[str] = None
    transcript_path: Optional[str] = None
    transcript_url: Optional[str] = None
    text: Optional[str] = None
    speakers: List[Dict[str, Any]] = Field(default_factory=list)
    segments: List[Dict[str, Any]] = Field(default_factory=list)
    profile_id: Optional[int] = None


class TranscriptExportRequest(BaseModel):
    destination: str
    format: str = "txt"
    note: Optional[str] = None


TranscriptionDetail = TranscriptDetail


class TranscriptionCreateResponse(BaseModel):
    id: int
    status: str
    original_filename: Optional[str] = None


class BatchTranscriptionCreateResponse(BaseModel):
    items: List[TranscriptionCreateResponse]


class HealthResponse(BaseModel):
    status: str
    app_name: str


class LiveSessionCreateRequest(BaseModel):
    model_size: Optional[str] = None
    device_preference: Optional[str] = None
    language: Optional[str] = None
    beam_size: Optional[int] = None


class LiveSessionCreateResponse(BaseModel):
    session_id: str
    model_size: Optional[str] = None
    device_preference: Optional[str] = None
    language: Optional[str] = None
    beam_size: Optional[int] = None


class LiveChunkResponse(BaseModel):
    session_id: str
    text: str
    duration: Optional[float] = None
    runtime_seconds: Optional[float] = None
    chunk_count: int
    model_size: Optional[str] = None
    device_preference: Optional[str] = None
    language: Optional[str] = None
    beam_size: Optional[int] = None
    segments: List[Dict] = Field(default_factory=list)
    new_segments: List[Dict] = Field(default_factory=list)
    new_text: Optional[str] = None
    dropped_chunks: int = 0


class LiveFinalizeRequest(BaseModel):
    model_size: Optional[str] = None
    device_preference: Optional[str] = None
    language: Optional[str] = None
    beam_size: Optional[int] = None
    destination_folder: Optional[str] = None
    filename: Optional[str] = None
    subject: Optional[str] = None


class LiveFinalizeResponse(BaseModel):
    session_id: str
    transcription_id: int
    text: str
    duration: Optional[float]
    runtime_seconds: Optional[float]
    output_folder: Optional[str]
    transcript_path: Optional[str]
    model_size: Optional[str]
    device_preference: Optional[str]
    language: Optional[str]
    beam_size: Optional[int]


class ModelPreparationRequest(BaseModel):
    model_size: Optional[str] = None
    device_preference: Optional[str] = None


class ModelPreparationStatus(BaseModel):
    model_size: str
    device_preference: str
    status: str
    progress: int
    message: str
    error: Optional[str] = None
    effective_device: Optional[str] = None


class SearchResponse(BaseModel):
    results: List[TranscriptDetail]
    total: int


@_enable_from_attributes
class PricingTierSchema(BaseModel):
    id: int
    slug: str
    name: str
    description: Optional[str] = None
    price_cents: int
    currency: str
    max_minutes: int
    perks: Optional[List[str]] = None
    is_active: bool = True


class CheckoutRequest(BaseModel):
    tier_slug: str
    customer_email: str
    transcription_id: Optional[int] = None


class PurchaseResponse(BaseModel):
    id: int
    status: str
    amount_cents: int
    currency: str
    payment_url: str
    tier_slug: str
    transcription_id: Optional[int] = None


class PurchaseDetail(PurchaseResponse):
    provider: Optional[str] = None
    extra_metadata: Optional[Dict[str, Any]] = None


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _normalize_tags(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [item for item in (part.strip() for part in value.split(",")) if item]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _ensure_dict_list(value: Any) -> List[Dict[str, Any]]:
    if not value:
        return []
    parsed: Any = value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return []
    if isinstance(parsed, dict):
        return [parsed]
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    return []


def _ensure_string_list(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            parsed = [value]
    else:
        parsed = value
    if isinstance(parsed, (list, tuple, set)):
        return [str(item) for item in parsed]
    return [str(parsed)]


def _coerce_status(value: Any) -> TranscriptionStatus:
    if isinstance(value, TranscriptionStatus):
        return value
    if isinstance(value, str):
        try:
            return TranscriptionStatus(value)
        except ValueError:
            mapping = {
                "queued": TranscriptionStatus.PENDING,
                "pending": TranscriptionStatus.PENDING,
                "processing": TranscriptionStatus.PROCESSING,
                "transcribing": TranscriptionStatus.PROCESSING,
                "completed": TranscriptionStatus.COMPLETED,
                "failed": TranscriptionStatus.FAILED,
            }
            lowered = value.lower()
            if lowered in mapping:
                return mapping[lowered]
    return TranscriptionStatus.PENDING


def build_transcription_detail(
    transcription: Any,
    *,
    include_segments: bool = True,
    transcript_url: Optional[str] = None,
) -> TranscriptDetail:
    job_id = getattr(transcription, "job_id", None)
    if not job_id:
        job_id = str(getattr(transcription, "id", ""))
    duration = getattr(transcription, "duration_seconds", None)
    if duration is None:
        duration = getattr(transcription, "duration", None)
    runtime = getattr(transcription, "runtime_seconds", None)
    debug_event_payloads = _ensure_dict_list(getattr(transcription, "debug_events", None))
    debug_events = [DebugEvent.model_validate(item) for item in debug_event_payloads]
    segments_raw = getattr(transcription, "segments", None)
    if not segments_raw:
        segments_raw = getattr(transcription, "speakers", None)
    segments = _ensure_dict_list(segments_raw)
    tags = _normalize_tags(getattr(transcription, "tags", None))
    title = getattr(transcription, "title", None)
    if not title:
        title = getattr(transcription, "subject", None)
    if not title:
        title = getattr(transcription, "original_filename", None)

    detail = TranscriptDetail(
        id=getattr(transcription, "id"),
        job_id=job_id,
        status=_coerce_status(getattr(transcription, "status", None)),
        title=title,
        language=getattr(transcription, "language", None),
        quality_profile=getattr(transcription, "quality_profile", None),
        created_at=getattr(transcription, "created_at"),
        updated_at=getattr(transcription, "updated_at"),
        completed_at=getattr(transcription, "completed_at", None),
        duration_seconds=_coerce_float(duration),
        runtime_seconds=_coerce_float(runtime),
        model_size=getattr(transcription, "model_size", None),
        device_preference=getattr(transcription, "device_preference", None),
        beam_size=getattr(transcription, "beam_size", None),
        subject=getattr(transcription, "subject", None),
        output_folder=getattr(transcription, "output_folder", None),
        premium_enabled=getattr(transcription, "premium_enabled", None),
        premium_notes=getattr(transcription, "premium_notes", None),
        premium_perks=_ensure_string_list(getattr(transcription, "premium_perks", None)),
        error_message=getattr(transcription, "error_message", None),
        debug_events=debug_events,
        tags=tags,
        original_filename=getattr(transcription, "original_filename", None),
        stored_path=getattr(transcription, "stored_path", None),
        audio_key=getattr(transcription, "audio_key", None) or getattr(transcription, "stored_path", None),
        transcript_key=getattr(transcription, "transcript_key", None),
        transcript_path=getattr(transcription, "transcript_path", None),
        transcript_url=transcript_url,
        text=getattr(transcription, "text", None),
        speakers=segments,
        segments=segments if include_segments else [],
        profile_id=getattr(transcription, "profile_id", None),
    )

    return detail
