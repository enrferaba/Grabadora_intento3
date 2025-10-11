"""FastAPI application entrypoint implementing SSE transcription endpoint."""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import AsyncGenerator, Dict, Optional

import json

try:  # pragma: no cover - optional dependency
    import structlog
except ImportError:  # pragma: no cover - fallback when structlog missing
    class _StructLogger:
        def __init__(self, name: str) -> None:
            self._logger = logging.getLogger(name)

        def info(self, msg: str, **kwargs) -> None:
            self._logger.info(msg, extra=kwargs)

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

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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

from sse_starlette.sse import EventSourceResponse

from app import auth
from app.auth import get_current_user
from app.config import get_settings
from app.database import session_scope
from app.schemas import TranscriptResponse, UserCreate, UserRead
from models.user import Profile, User
from queue import tasks
from storage.s3 import S3StorageClient

settings = get_settings()

logging.basicConfig(level=logging.INFO)
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
)
logger = structlog.get_logger(__name__)

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
async def login(form_data: auth.OAuth2PasswordRequestForm = Depends()) -> dict:
    return auth.login(form_data)


@app.post("/users", response_model=UserRead, status_code=201)
async def create_user(payload: UserCreate) -> UserRead:
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
        QUEUE_LENGTH.set(queue.count)
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
                }
            )
            yield {"event": "completed", "data": payload}
            break
        if status == "failed":
            yield {"event": "error", "data": job.id}
            break
        await asyncio.sleep(0.5)


@app.post("/transcribe", response_model=TranscriptResponse)
async def create_transcription_job(
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    user: User = Depends(get_current_user),
) -> TranscriptResponse:
    redis = Redis.from_url(settings.redis_url)
    queue = Queue(settings.rq_default_queue, connection=redis)

    storage = S3StorageClient()
    storage.ensure_buckets()

    audio_key = f"{user.id}/{uuid.uuid4()}-{file.filename}"
    storage.upload_audio(file.file, audio_key)

    job = queue.enqueue(
        tasks.transcribe_job,
        audio_key,
        language=language,
        profile_id=user.profiles[0].id if user.profiles else None,
    )
    QUEUE_LENGTH.set(queue.count)

    return TranscriptResponse(job_id=job.id, status="queued")


@app.get("/transcribe/{job_id}")
async def stream_transcription(job_id: str, user: User = Depends(get_current_user)) -> EventSourceResponse:
    redis = Redis.from_url(settings.redis_url)

    async def event_generator() -> AsyncGenerator[Dict[str, str], None]:
        async for event in _stream_job(job_id, redis):
            yield event

    return EventSourceResponse(event_generator())


@app.get("/healthz")
async def healthcheck() -> JSONResponse:
    _sample_gpu_usage()
    return JSONResponse({"status": "ok", "time": datetime.utcnow().isoformat()})
