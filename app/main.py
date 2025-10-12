"""FastAPI application entrypoint implementing SSE transcription endpoint."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, Optional

try:  # pragma: no cover - optional dependency
    from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse, JSONResponse, Response
    from fastapi.staticfiles import StaticFiles
    from starlette.requests import ClientDisconnect
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

    class ClientDisconnect(Exception):  # type: ignore
        pass

if TYPE_CHECKING:  # pragma: no cover - typing helpers for optional FastAPI dependency
    from fastapi import FastAPI as FastAPIApp
    from fastapi.responses import HTMLResponse as HTMLResponseType
    from fastapi.responses import JSONResponse as JSONResponseType
    from fastapi.responses import Response as ResponseType
else:  # graceful fallbacks for static analysis when FastAPI is unavailable at runtime
    FastAPIApp = Any
    HTMLResponseType = Any
    JSONResponseType = Any
    ResponseType = Any

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
    from redis import Redis as RedisClient
except ImportError:  # pragma: no cover
    RedisClient = None

try:  # pragma: no cover - optional dependency
    from rq import Queue as RQQueue
except ImportError:  # pragma: no cover
    RQQueue = None

from app import auth
from app.auth import AuthenticatedUser, get_current_user
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
from taskqueue.fallback import InMemoryQueue, InMemoryRedis
from storage.s3 import S3StorageClient

settings = get_settings()

_fallback_queue: InMemoryQueue | None = None


def _obtain_queue() -> tuple[object, bool]:
    """Return a queue instance and whether it uses the in-memory fallback."""

    global _fallback_queue
    preferred_backend = getattr(settings, "queue_backend", "auto")
    if preferred_backend == "memory":
        if _fallback_queue is None:
            _fallback_queue = InMemoryQueue(settings.rq_default_queue, connection=InMemoryRedis.from_url("memory://local"))
        return _fallback_queue, True
    force_redis = preferred_backend == "redis"
    if RedisClient is None or RQQueue is None:  # dependencies missing entirely
        if force_redis:
            raise HTTPException(status_code=503, detail="Redis backend requerido pero no disponible")
        if _fallback_queue is None:
            _fallback_queue = InMemoryQueue(settings.rq_default_queue, connection=InMemoryRedis.from_url("memory://local"))
        return _fallback_queue, True

    try:
        redis_conn = RedisClient.from_url(settings.redis_url)
        if hasattr(redis_conn, "ping"):
            redis_conn.ping()
        return RQQueue(settings.rq_default_queue, connection=redis_conn), False
    except Exception as exc:
        if force_redis:
            logger.error(
                "Redis backend required but unavailable", extra={"detail": str(exc)}
            )
            raise HTTPException(status_code=503, detail="Redis backend no disponible") from exc
        logger.warning(
            "Redis/RQ unavailable, enabling in-memory queue fallback", extra={"detail": str(exc)}
        )
        if _fallback_queue is None:
            _fallback_queue = InMemoryQueue(settings.rq_default_queue, connection=InMemoryRedis.from_url("memory://local"))
        return _fallback_queue, True


def _queue_length(queue: object) -> int:
    count_attr = getattr(queue, "count", 0)
    try:
        return int(count_attr()) if callable(count_attr) else int(count_attr)
    except Exception:  # pragma: no cover - defensive
        return 0


# Backwards-compatible aliases for tests/monkeypatching ---------------------
Queue = RQQueue if RQQueue is not None else InMemoryQueue  # type: ignore[assignment]
Redis = RedisClient if RedisClient is not None else InMemoryRedis  # type: ignore[assignment]

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

app: FastAPIApp | None = None  # type: ignore[misc]
if FastAPI is not None:
    app = FastAPI(title=settings.api_title, version=settings.api_version, description=settings.api_description)
    allow_origins: List[str] = []
    frontend_origin = getattr(settings, "frontend_origin", None)
    if frontend_origin:
        allow_origins = ["*"] if frontend_origin == "*" else [frontend_origin]
    elif getattr(settings, "queue_backend", "auto") == "memory":
        allow_origins = ["*"]
    if allow_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allow_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    Instrumentator(namespace=settings.prometheus_namespace).instrument(app).expose(app)

API_ERRORS = Counter("api_errors_total", "Total API errors", namespace=settings.prometheus_namespace)
QUEUE_LENGTH = Gauge("queue_length", "Number of queued transcription jobs", namespace=settings.prometheus_namespace)
GPU_USAGE = Gauge("gpu_memory_usage_bytes", "Approximate GPU memory usage", namespace=settings.prometheus_namespace)

SPA_MOUNTED = False


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
        transcript_url = storage.create_presigned_url(
            transcript.transcript_key,
            expires_in=getattr(settings, "s3_presigned_ttl", 86400),
        )
    segments_raw = getattr(transcript, "segments", None)
    try:
        segments = json.loads(segments_raw) if segments_raw else []
    except json.JSONDecodeError:
        segments = []
    return TranscriptDetail(
        **summary.model_dump(),
        audio_key=transcript.audio_key,
        transcript_key=getattr(transcript, "transcript_key", None),
        transcript_url=transcript_url,
        segments=segments,
        error_message=getattr(transcript, "error_message", None),
        profile_id=getattr(transcript, "profile_id", None),
    )


def _spa_index() -> HTMLResponseType:
    if FRONTEND_DIST.exists():
        return HTMLResponse((FRONTEND_DIST / "index.html").read_text(encoding="utf-8"))
    if FRONTEND_SOURCE.exists():
        return HTMLResponse(FRONTEND_SOURCE.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Grabadora</h1><p>Frontend assets missing.</p>")


async def _stream_job(
    job_id: str,
    redis: object | None = None,
    *,
    expected_user_id: int | None = None,
) -> AsyncGenerator[Dict[str, str], None]:
    if redis is not None:
        queue = Queue(name=settings.rq_default_queue, connection=redis)  # type: ignore[call-arg]
    else:
        queue, _ = _obtain_queue()
    job = queue.fetch_job(job_id)
    if job is None:
        yield {"event": "error", "data": json.dumps({"detail": "job-not-found"})}
        return

    meta: Dict = getattr(job, "meta", {}) or {}
    if expected_user_id is not None and meta.get("user_id") not in {expected_user_id, None}:
        yield {"event": "error", "data": json.dumps({"detail": "job-not-found"})}
        return

    last_progress = int(meta.get("progress", 0) or 0)
    last_snapshot_progress = last_progress
    snapshot_sent = last_progress == 0
    loop = asyncio.get_running_loop()
    heartbeat_interval = 10.0
    last_heartbeat = loop.time()

    while True:
        try:
            job.refresh()
        except Exception:  # pragma: no cover - defensive
            pass

        try:
            status = job.get_status(refresh=False)
        except Exception:  # pragma: no cover - defensive
            status = meta.get("status", "unknown")

        meta = getattr(job, "meta", {}) or {}
        if expected_user_id is not None and meta.get("user_id") not in {expected_user_id, None}:
            yield {"event": "error", "data": json.dumps({"detail": "job-not-found"})}
            return

        queue_size = _queue_length(queue)
        try:
            QUEUE_LENGTH.set(float(queue_size or 0))
        except Exception:  # pragma: no cover - defensive
            QUEUE_LENGTH.set(0)
        _sample_gpu_usage()

        token_payload = meta.get("last_token")
        if isinstance(token_payload, dict):
            token_payload_text = json.dumps(token_payload)
        else:
            token_payload_text = token_payload

        progress_value = int(meta.get("progress", 0) or 0)
        snapshot_text = meta.get("transcript_so_far")
        if snapshot_text and (not snapshot_sent or progress_value - last_snapshot_progress >= 25):
            segments_payload = meta.get("segments_partial")
            if isinstance(segments_payload, str):
                try:
                    segments_payload = json.loads(segments_payload)
                except json.JSONDecodeError:
                    segments_payload = None
            snapshot_body: Dict[str, Any] = {
                "job_id": job.id,
                "text": snapshot_text,
                "progress": progress_value,
            }
            if isinstance(segments_payload, list):
                snapshot_body["segments"] = segments_payload
            yield {"event": "snapshot", "data": json.dumps(snapshot_body)}
            snapshot_sent = True
            last_snapshot_progress = progress_value

        if progress_value > last_progress and token_payload_text:
            last_progress = progress_value
            yield {"event": "delta", "data": token_payload_text}

        meta_status = meta.get("status") or status
        if meta_status == "completed":
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

        if meta_status == "failed" or status == "failed":
            error_payload = json.dumps(
                {
                    "job_id": job.id,
                    "detail": meta.get("error_message", "unknown"),
                }
            )
            yield {"event": "error", "data": error_payload}
            break

        now = loop.time()
        if now - last_heartbeat >= heartbeat_interval:
            heartbeat_payload = json.dumps(
                {
                    "job_id": job.id,
                    "status": meta_status,
                    "progress": progress_value,
                }
            )
            yield {"event": "heartbeat", "data": heartbeat_payload}
            last_heartbeat = now

        await asyncio.sleep(0.5)


if app is not None:

    if StaticFiles is not None and FRONTEND_DIST.exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="spa-assets")
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="spa")
        SPA_MOUNTED = True

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponseType:
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
            return UserRead.model_validate(user)

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
        user: AuthenticatedUser = Depends(get_current_user),
    ) -> TranscriptResponse:
        if profile not in QUALITY_PROFILES:
            raise HTTPException(status_code=400, detail="Invalid quality profile")
        queue, used_fallback = _obtain_queue()

        storage = S3StorageClient()
        storage.ensure_buckets()

        audio_key = f"{user.id}/{uuid.uuid4()}-{file.filename}"
        storage.upload_audio(file.file, audio_key)

        primary_profile_id = user.profiles[0].id if getattr(user, "profiles", []) else None
        enqueued_at = datetime.utcnow().isoformat()
        job = queue.enqueue(  # type: ignore[call-arg]
            tasks.transcribe_job,
            audio_key,
            language=language,
            profile_id=primary_profile_id,
            user_id=user.id,
            quality_profile=profile,
            meta={
                "status": "queued",
                "progress": 0,
                "segment": 0,
                "user_id": user.id,
                "quality_profile": profile,
                "queued_at": enqueued_at,
                "updated_at": enqueued_at,
            },
            job_timeout=getattr(settings, "rq_job_timeout", None),
            result_ttl=getattr(settings, "rq_result_ttl", 86400),
            failure_ttl=getattr(settings, "rq_failure_ttl", 3600),
        )
        if getattr(job, "meta", None) is not None:
            job.meta.setdefault("status", "queued")
            job.meta.setdefault("progress", 0)
            job.meta.setdefault("segment", 0)
            job.meta.setdefault("user_id", user.id)
            job.meta.setdefault("quality_profile", profile)
            job.meta.setdefault("queued_at", enqueued_at)
            job.meta["updated_at"] = enqueued_at
            try:
                job.save_meta()
            except Exception:  # pragma: no cover - defensive when using fallback queue
                pass
        try:
            QUEUE_LENGTH.set(float(_queue_length(queue)))
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
            if getattr(job, "meta", None) is not None:
                job.meta["transcript_id"] = transcript.id
                try:
                    job.save_meta()
                except Exception:  # pragma: no cover - fallback queue
                    pass
            log_payload = {
                "job_id": job.id,
                "audio_key": audio_key,
                "user_id": user.id,
                "quality_profile": profile,
                "meta": meta_notes,
            }
            if used_fallback:
                log_payload["queue_backend"] = "memory"
            logger.info("Queued transcription job", extra=log_payload)

        return TranscriptResponse(job_id=job.id, status="queued", quality_profile=profile)

    @app.get("/transcribe/{job_id}")
    async def stream_transcription(
        job_id: str, user: AuthenticatedUser = Depends(get_current_user)
    ) -> EventSourceResponse:

        async def event_generator() -> AsyncGenerator[Dict[str, str], None]:
            try:
                async for event in _stream_job(job_id, expected_user_id=user.id):
                    yield event
            except ClientDisconnect:  # pragma: no cover - network race
                logger.info("SSE client disconnected", extra={"job_id": job_id, "user_id": user.id})
            except asyncio.CancelledError:  # pragma: no cover - shutdown handling
                logger.info("SSE stream cancelled", extra={"job_id": job_id, "user_id": user.id})
                raise

        return EventSourceResponse(
            event_generator(),
            ping=10.0,
            retry=5000,
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get("/jobs/{job_id}")
    async def get_job_status(job_id: str, user: AuthenticatedUser = Depends(get_current_user)) -> JSONResponse:
        queue, _ = _obtain_queue()
        job = queue.fetch_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        meta: Dict = getattr(job, "meta", {}) or {}
        if meta.get("user_id") not in {None, user.id}:
            raise HTTPException(status_code=404, detail="Job not found")
        try:
            status = meta.get("status") or job.get_status(refresh=False)
        except Exception:  # pragma: no cover - defensive
            status = meta.get("status", "unknown")
        payload: Dict[str, Optional[object]] = {
            "job_id": job.id,
            "status": status,
            "progress": meta.get("progress", 0),
            "segment": meta.get("segment"),
            "transcript_id": meta.get("transcript_id"),
            "quality_profile": meta.get("quality_profile"),
            "updated_at": meta.get("updated_at"),
        }
        if meta.get("error_message"):
            payload["error_message"] = meta.get("error_message")
        transcript_key = meta.get("transcript_key")
        if transcript_key:
            storage = S3StorageClient()
            payload["transcript_url"] = storage.create_presigned_url(
                transcript_key,
                expires_in=getattr(settings, "s3_presigned_ttl", 86400),
            )
        return JSONResponse(payload)

    @app.get("/transcripts", response_model=List[TranscriptSummary])
    async def list_transcripts(
        search: Optional[str] = Query(None, description="Texto libre para filtrar títulos o etiquetas"),
        status: Optional[str] = Query(None, description="Filtra por estado"),
        user: AuthenticatedUser = Depends(get_current_user),
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
    async def get_transcript(
        transcript_id: int, user: AuthenticatedUser = Depends(get_current_user)
    ) -> TranscriptDetail:
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
        user: AuthenticatedUser = Depends(get_current_user),
    ) -> ResponseType:
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
        user: AuthenticatedUser = Depends(get_current_user),
    ) -> JSONResponseType:
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
    async def healthcheck() -> JSONResponseType:
        _sample_gpu_usage()
        return JSONResponse({"status": "ok", "time": datetime.utcnow().isoformat()})

    if not SPA_MOUNTED:
        @app.get("/", response_class=HTMLResponse)
        async def root() -> HTMLResponseType:
            return _spa_index()

        @app.get("/{full_path:path}", response_class=HTMLResponse)
        async def spa_router(full_path: str) -> HTMLResponseType:
            reserved_prefixes = (
                "docs",
                "redoc",
                "openapi.json",
                "metrics",
                "healthz",
                "auth",
                "users",
                "transcribe",
                "transcripts",
                "jobs",
            )
            if any(full_path.startswith(prefix) for prefix in reserved_prefixes):
                raise HTTPException(status_code=404, detail="Not Found")
            return _spa_index()


def create_app() -> FastAPIApp:
    if app is None:
        raise RuntimeError("FastAPI is not available")
    return app
