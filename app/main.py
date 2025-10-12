"""FastAPI application entrypoint implementing SSE transcription endpoint."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional

try:  # pragma: no cover - optional dependency
    from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse, JSONResponse, Response
    from fastapi.staticfiles import StaticFiles
except ImportError:  # pragma: no cover
    FastAPI = None  # type: ignore

    def Depends(dependency=None):  # type: ignore
        raise RuntimeError("FastAPI is required for API dependencies")

    class UploadFile:  # type: ignore
        def __init__(self, filename: str = "", file=None) -> None:
            self.filename = filename
            self.file = file

    class File:  # type: ignore
        def __call__(self, *args, **kwargs):
            raise RuntimeError("FastAPI is required for file uploads")

    class Form:  # type: ignore
        def __call__(self, *args, **kwargs):
            raise RuntimeError("FastAPI is required for forms")

    class HTTPException(Exception):  # type: ignore
        def __init__(self, status_code: int, detail: str) -> None:
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class Request:  # type: ignore
        pass

    class JSONResponse(dict):  # type: ignore
        pass

    class HTMLResponse(str):  # type: ignore
        pass

    class Response(dict):  # type: ignore
        pass

    class Query:  # type: ignore
        def __init__(self, default=None, *_, **__):
            self.default = default

    class Body:  # type: ignore
        def __init__(self, default=None, *_, **__):
            self.default = default

    class StaticFiles:  # type: ignore
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError("FastAPI is required for static file serving")

    class CORSMiddleware:  # type: ignore
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError("FastAPI is required for CORS middleware")

try:  # pragma: no cover - optional dependency
    from sse_starlette.sse import EventSourceResponse
except ImportError:  # pragma: no cover
    class EventSourceResponse(JSONResponse):  # type: ignore[misc]
        media_type = "text/event-stream"

        def __init__(self, *args, **kwargs) -> None:
            super().__init__(
                {"detail": "sse-starlette must be installed to stream events"},
                status_code=500,
            )

try:  # pragma: no cover - optional dependency
    from prometheus_client import Counter, Gauge
except ImportError:  # pragma: no cover
    class Counter:  # type: ignore
        def __init__(self, *args, **kwargs) -> None:
            pass

        def inc(self, amount: int = 1) -> None:  # pragma: no cover
            pass

    class Gauge:  # type: ignore
        def __init__(self, *args, **kwargs) -> None:
            pass

        def set(self, value: float) -> None:  # pragma: no cover
            pass

try:  # pragma: no cover - optional dependency
    from prometheus_fastapi_instrumentator import Instrumentator
except ImportError:  # pragma: no cover
    class Instrumentator:  # type: ignore
        def __init__(self, *args, **kwargs) -> None:
            pass

        def instrument(self, app):  # pragma: no cover
            return self

        def expose(self, app):  # pragma: no cover
            return self

try:  # pragma: no cover - optional dependency
    from redis import Redis
except ImportError:  # pragma: no cover
    class Redis:  # type: ignore
        @staticmethod
        def from_url(url: str):  # pragma: no cover
            raise RuntimeError("redis package is not installed")

try:  # pragma: no cover - optional dependency
    from rq import Queue
except ImportError:  # pragma: no cover
    class Queue:  # type: ignore
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError("rq package is not installed")

        @property
        def count(self) -> int:  # pragma: no cover
            return 0

        def fetch_job(self, job_id: str):  # pragma: no cover
            return None

        def enqueue(self, *args, **kwargs):  # pragma: no cover
            raise RuntimeError("rq package is not installed")

from app import auth
from app.auth import get_current_user
from app.config import get_settings
from app.database import session_scope
from app.schemas import (
    TranscriptDetail,
    TranscriptExportRequest,
    TranscriptResponse,
    TranscriptSummary,
    UserCreate,
    UserRead,
)
try:  # pragma: no cover - optional dependency
    from models.user import Profile, Transcript, User
except ImportError:  # pragma: no cover
    class Profile:  # type: ignore
        def __init__(self, name: str, description: str | None = None) -> None:
            self.id = 0
            self.name = name
            self.description = description

    class Transcript:  # type: ignore
        def __init__(self) -> None:
            self.id = 0
            self.job_id = ""
            self.status = "queued"
            self.audio_key = ""
            self.transcript_key: str | None = None
            self.language: str | None = None
            self.quality_profile: str | None = None
            self.title: str | None = None
            self.tags: str | None = None
            self.duration_seconds: float | None = None
            self.segments: str | None = None
            self.created_at = datetime.utcnow()
            self.updated_at = datetime.utcnow()
            self.completed_at: datetime | None = None
            self.profile_id: int | None = None

    class User:  # type: ignore
        def __init__(self) -> None:
            self.id = 0
            self.email = ""
            self.profiles: list = []

from taskqueue import tasks
from storage.s3 import S3StorageClient

settings = get_settings()

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
FRONTEND_SOURCE = Path(__file__).resolve().parent.parent / "frontend" / "index.html"

QUALITY_PROFILES = {
    "fast": {
        "label": "Rápido (int8)",
        "description": "Máxima velocidad, ideal para notas rápidas",
    },
    "balanced": {
        "label": "Equilibrado (float16)",
        "description": "Buen balance entre precisión y coste",
    },
    "precise": {
        "label": "Preciso (float32)",
        "description": "Máxima fidelidad para grabaciones críticas",
    },
}

try:  # pragma: no cover - optional dependency
    import structlog
except ImportError:  # pragma: no cover - fallback when structlog missing
    class _StructLogger:
        def __init__(self, name: str) -> None:
            self._logger = logging.getLogger(name)

        def info(self, msg: str, **kwargs) -> None:
            self._logger.info(msg, extra=kwargs)

        def warning(self, msg: str, **kwargs) -> None:
            self._logger.warning(msg, extra=kwargs)

        def exception(self, msg: str, exc_info: Exception | None = None) -> None:
            self._logger.exception(msg, exc_info=exc_info)

    class _StructlogModule:
        @staticmethod
        def configure(*args, **kwargs) -> None:  # pragma: no cover
            logging.basicConfig(level=logging.INFO)

        @staticmethod
        def get_logger(name: str) -> _StructLogger:
            return _StructLogger(name)

    structlog = _StructlogModule()  # type: ignore

logging.basicConfig(level=logging.INFO)
processors = []
if hasattr(structlog, "processors"):
    processors = [
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
structlog.configure(processors=processors)
logger = structlog.get_logger(__name__)

app: FastAPI | None = None  # type: ignore[misc]
if FastAPI is not None:
    app = FastAPI(title=settings.api_title, version=settings.api_version, description=settings.api_description)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    Instrumentator(namespace=settings.prometheus_namespace).instrument(app).expose(app)

API_ERRORS = Counter("api_errors_total", "Total API errors", namespace=settings.prometheus_namespace)
QUEUE_LENGTH = Gauge("queue_length", "Number of queued transcription jobs", namespace=settings.prometheus_namespace)
GPU_USAGE = Gauge("gpu_memory_usage_bytes", "Approximate GPU memory usage", namespace=settings.prometheus_namespace)


def _sample_gpu_usage() -> None:
    try:
        import torch

        if torch.cuda.is_available():
            GPU_USAGE.set(float(torch.cuda.memory_allocated()))
        else:
            GPU_USAGE.set(0)
    except Exception:
        GPU_USAGE.set(0)


def _split_tags(raw: Optional[str | List[str]]) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        source = raw
    else:
        source = [item.strip() for item in raw.split(",")]
    return [item for item in (value.strip() for value in source) if item]


def _join_tags(tags: Optional[List[str]]) -> Optional[str]:
    if not tags:
        return None
    return ",".join(tags)


def _transcript_to_summary(transcript: Transcript) -> TranscriptSummary:
    tags = _split_tags(getattr(transcript, "tags", None))
    duration_value = getattr(transcript, "duration_seconds", None)
    duration_float = float(duration_value) if duration_value is not None else None
    return TranscriptSummary(
        id=transcript.id,
        job_id=transcript.job_id,
        status=transcript.status,
        title=getattr(transcript, "title", None),
        language=getattr(transcript, "language", None),
        quality_profile=getattr(transcript, "quality_profile", None),
        created_at=transcript.created_at,
        updated_at=transcript.updated_at,
        completed_at=getattr(transcript, "completed_at", None),
        duration_seconds=duration_float,
        tags=tags,
    )


def _transcript_to_detail(transcript: Transcript, *, include_url: bool = True) -> TranscriptDetail:
    summary = _transcript_to_summary(transcript)
    storage = S3StorageClient()
    transcript_url = None
    if include_url and getattr(transcript, "transcript_key", None):
        transcript_url = storage.create_presigned_url(transcript.transcript_key)
    segments_raw = getattr(transcript, "segments", None)
    try:
        segments = json.loads(segments_raw) if segments_raw else []
    except json.JSONDecodeError:
        segments = []
    return TranscriptDetail(
        **summary.dict(),
        audio_key=transcript.audio_key,
        transcript_key=getattr(transcript, "transcript_key", None),
        transcript_url=transcript_url,
        segments=segments,
        error_message=getattr(transcript, "error_message", None),
        profile_id=getattr(transcript, "profile_id", None),
    )


def _spa_index() -> HTMLResponse:
    if FRONTEND_DIST.exists():
        return HTMLResponse((FRONTEND_DIST / "index.html").read_text(encoding="utf-8"))
    if FRONTEND_SOURCE.exists():
        return HTMLResponse(FRONTEND_SOURCE.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Grabadora</h1><p>Frontend assets missing.</p>")


async def _stream_job(job_id: str, redis: Redis) -> AsyncGenerator[Dict[str, str], None]:
    queue = Queue(name=settings.rq_default_queue, connection=redis)
    job = queue.fetch_job(job_id)
    if job is None:
        yield {"event": "error", "data": "job-not-found"}
        return

    last_progress = 0
    while True:
        job.refresh()
        status = job.get_status(refresh=False)
        meta: Dict = job.meta or {}
        queue_count_attr = getattr(queue, "count", 0)
        queue_size = queue_count_attr() if callable(queue_count_attr) else queue_count_attr
        try:
            QUEUE_LENGTH.set(float(queue_size or 0))
        except Exception:  # pragma: no cover - defensive
            QUEUE_LENGTH.set(0)
        _sample_gpu_usage()
        if meta.get("progress", 0) > last_progress and meta.get("last_token"):
            last_progress = meta["progress"]
            yield {"event": "delta", "data": meta["last_token"]}
        if meta.get("status") == "completed":
            payload = json.dumps(
                {
                    "job_id": job.id,
                    "transcript_key": meta.get("transcript_key"),
                    "language": meta.get("language"),
                    "duration": meta.get("duration"),
                    "quality_profile": meta.get("quality_profile"),
                }
            )
            yield {"event": "completed", "data": payload}
            break
        if status == "failed":
            error_payload = json.dumps({"job_id": job.id, "detail": meta.get("error_message", "unknown")})
            yield {"event": "error", "data": error_payload}
            break
        await asyncio.sleep(0.5)


if app is not None:

    if StaticFiles is not None and FRONTEND_DIST.exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="spa-assets")

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        API_ERRORS.inc()
        logger.exception("Unhandled exception", exc_info=exc)
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

    @app.on_event("startup")
    async def startup_event() -> None:
        storage = S3StorageClient()
        storage.ensure_buckets()

    @app.post("/auth/token")
    async def login(form_data: auth.OAuth2PasswordRequestForm = Depends()) -> dict:  # type: ignore[assignment]
        return auth.login(form_data)

    @app.post("/auth/signup", response_model=UserRead, status_code=201)
    async def signup(payload: UserCreate) -> UserRead:
        with session_scope() as session:
            existing = session.query(User).filter(User.email == payload.email).one_or_none()
            if existing:
                raise HTTPException(status_code=400, detail="User already exists")
            user = User(email=payload.email, hashed_password=auth.get_password_hash(payload.password))
            profile = Profile(name="Default", description="Primary profile")
            user.profiles.append(profile)
            session.add(user)
            session.flush()
            session.refresh(user)
            return UserRead.from_orm(user)

    @app.post("/users", response_model=UserRead, status_code=201)
    async def create_user(payload: UserCreate) -> UserRead:
        return await signup(payload)

    @app.post("/transcribe", response_model=TranscriptResponse)
    async def create_transcription_job(
        file: UploadFile = File(...),
        language: Optional[str] = Form(None),
        profile: str = Form("balanced"),
        title: Optional[str] = Form(None),
        tags: Optional[str] = Form(None),
        diarization: bool = Form(False),
        word_timestamps: bool = Form(True),
        user: User = Depends(get_current_user),
    ) -> TranscriptResponse:
        if profile not in QUALITY_PROFILES:
            raise HTTPException(status_code=400, detail="Invalid quality profile")
        redis = Redis.from_url(settings.redis_url)
        queue = Queue(settings.rq_default_queue, connection=redis)

        storage = S3StorageClient()
        storage.ensure_buckets()

        audio_key = f"{user.id}/{uuid.uuid4()}-{file.filename}"
        storage.upload_audio(file.file, audio_key)

        primary_profile_id = user.profiles[0].id if getattr(user, "profiles", []) else None
        job = queue.enqueue(
            tasks.transcribe_job,
            audio_key,
            language=language,
            profile_id=primary_profile_id,
            user_id=user.id,
            quality_profile=profile,
        )
        try:
            QUEUE_LENGTH.set(float(queue.count))
        except Exception:  # pragma: no cover - defensive
            QUEUE_LENGTH.set(0)

        filename = file.filename or "audio.wav"
        derived_title = title or Path(filename).stem
        tag_list = _split_tags(tags)
        meta_notes = {
            "diarization": diarization,
            "word_timestamps": word_timestamps,
        }
        with session_scope() as session:
            transcript = Transcript(
                user_id=user.id,
                profile_id=primary_profile_id,
                job_id=job.id,
                audio_key=audio_key,
                status="queued",
                language=language,
                quality_profile=profile,
                title=derived_title,
                tags=_join_tags(tag_list),
            )
            transcript.segments = json.dumps([])
            session.add(transcript)
            session.flush()
            logger.info(
                "Queued transcription job",
                extra={
                    "job_id": job.id,
                    "audio_key": audio_key,
                    "user_id": user.id,
                    "quality_profile": profile,
                    "meta": meta_notes,
                },
            )

        return TranscriptResponse(job_id=job.id, status="queued", quality_profile=profile)

    @app.get("/transcribe/{job_id}")
    async def stream_transcription(job_id: str, user: User = Depends(get_current_user)) -> EventSourceResponse:
        redis = Redis.from_url(settings.redis_url)

        async def event_generator() -> AsyncGenerator[Dict[str, str], None]:
            async for event in _stream_job(job_id, redis):
                yield event

        return EventSourceResponse(event_generator())

    @app.get("/transcripts", response_model=List[TranscriptSummary])
    async def list_transcripts(
        search: Optional[str] = Query(None, description="Texto libre para filtrar títulos o etiquetas"),
        status: Optional[str] = Query(None, description="Filtra por estado"),
        user: User = Depends(get_current_user),
    ) -> List[TranscriptSummary]:
        with session_scope() as session:
            items = (
                session.query(Transcript)
                .filter(Transcript.user_id == user.id)
                .order_by(Transcript.created_at.desc())
                .all()
            )
        results: List[TranscriptSummary] = []
        for transcript in items:
            if status and transcript.status != status:
                continue
            tags = _split_tags(transcript.tags)
            if search:
                haystack = " ".join(filter(None, [transcript.title, transcript.language, ",".join(tags)]))
                if search.lower() not in haystack.lower():
                    continue
            results.append(_transcript_to_summary(transcript))
        return results

    @app.get("/transcripts/{transcript_id}", response_model=TranscriptDetail)
    async def get_transcript(transcript_id: int, user: User = Depends(get_current_user)) -> TranscriptDetail:
        with session_scope() as session:
            transcript = session.query(Transcript).filter(Transcript.id == transcript_id, Transcript.user_id == user.id).one_or_none()
            if transcript is None:
                raise HTTPException(status_code=404, detail="Transcript not found")
        return _transcript_to_detail(transcript)

    def _segments_to_srt(segments: List[dict]) -> str:
        lines: List[str] = []
        for idx, segment in enumerate(segments, start=1):
            start = float(segment.get("start", 0))
            end = float(segment.get("end", 0))
            text = segment.get("text", "").strip()
            start_ts = str(datetime.utcfromtimestamp(start).time())[:12]
            end_ts = str(datetime.utcfromtimestamp(end).time())[:12]
            lines.extend([str(idx), f"{start_ts.replace('.', ',')} --> {end_ts.replace('.', ',')}", text, ""])
        return "\n".join(lines).strip()

    @app.get("/transcripts/{transcript_id}/download")
    async def download_transcript(
        transcript_id: int,
        format: str = Query("txt", enum=["txt", "md", "srt"]),
        user: User = Depends(get_current_user),
    ) -> Response:
        with session_scope() as session:
            transcript = session.query(Transcript).filter(Transcript.id == transcript_id, Transcript.user_id == user.id).one_or_none()
            if transcript is None or not transcript.transcript_key:
                raise HTTPException(status_code=404, detail="Transcript not found")
        storage = S3StorageClient()
        content = storage.download_transcript(transcript.transcript_key)
        if content is None:
            raise HTTPException(status_code=404, detail="Transcript blob missing")
        filename = f"transcript-{transcript.id}.{format}"
        media_type = "text/plain"
        if format == "md":
            header = f"# {transcript.title or 'Transcripción'}\n\n"
            details = f"- Idioma: {transcript.language or 'desconocido'}\n- Perfil: {transcript.quality_profile or 'n/a'}\n\n"
            content = header + details + content
        elif format == "srt":
            detail = _transcript_to_detail(transcript, include_url=False)
            content = _segments_to_srt(detail.segments)
            media_type = "application/x-subrip"
        response = Response(content=content, media_type=media_type)
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"
        return response

    @app.post("/transcripts/{transcript_id}/export")
    async def export_transcript(
        transcript_id: int,
        payload: TranscriptExportRequest = Body(...),
        user: User = Depends(get_current_user),
    ) -> JSONResponse:
        allowed_destinations = {"notion", "trello", "webhook"}
        if payload.destination not in allowed_destinations:
            raise HTTPException(status_code=400, detail="Unsupported destination")
        with session_scope() as session:
            transcript = session.query(Transcript).filter(Transcript.id == transcript_id, Transcript.user_id == user.id).one_or_none()
            if transcript is None:
                raise HTTPException(status_code=404, detail="Transcript not found")
        logger.info(
            "Exporting transcript",
            extra={
                "transcript_id": transcript_id,
                "destination": payload.destination,
                "format": payload.format,
            },
        )
        return JSONResponse(
            {
                "status": "queued",
                "destination": payload.destination,
                "format": payload.format,
            }
        )

    @app.get("/healthz")
    async def healthcheck() -> JSONResponse:
        _sample_gpu_usage()
        return JSONResponse({"status": "ok", "time": datetime.utcnow().isoformat()})

    @app.get("/", response_class=HTMLResponse)
    async def root() -> HTMLResponse:
        return _spa_index()

    @app.get("/{full_path:path}", response_class=HTMLResponse)
    async def spa_router(full_path: str) -> HTMLResponse:
        reserved_prefixes = ("docs", "redoc", "openapi.json", "metrics", "healthz", "auth", "users", "transcribe", "transcripts")
        if any(full_path.startswith(prefix) for prefix in reserved_prefixes):
            raise HTTPException(status_code=404, detail="Not Found")
        return _spa_index()
