"""RQ tasks responsible for executing transcription workloads."""
from __future__ import annotations

import json
import logging
import tempfile
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
try:  # pragma: no cover - optional dependency
    from rq import get_current_job as rq_get_current_job
except ImportError:  # pragma: no cover
    rq_get_current_job = None

from app.config import get_settings
from app.database import session_scope
from models.user import Transcript
from services.transcription import TranscriptionService
from storage.s3 import S3StorageClient

logger = logging.getLogger(__name__)


_current_job_ctx: ContextVar[Any | None] = ContextVar("grabadora_current_job", default=None)


def set_current_job(job: Any | None) -> None:
    _current_job_ctx.set(job)


def clear_current_job() -> None:
    _current_job_ctx.set(None)


def get_current_job():  # type: ignore[override]
    if rq_get_current_job is not None:  # pragma: no branch - small helper
        try:
            job = rq_get_current_job()
            if job is not None:
                return job
        except Exception:  # pragma: no cover - defensive when Redis is down
            pass
    return _current_job_ctx.get()


def _update_job_meta(meta: dict) -> None:
    job = get_current_job()
    if job is None:
        return
    job.meta.setdefault("progress", 0)
    job.meta.setdefault("segment", 0)
    job.meta.update(meta)
    job.meta["updated_at"] = datetime.utcnow().isoformat()
    try:
        job.save_meta()
    except Exception:  # pragma: no cover - fallback queue has no persistence
        pass


def _select_quantization(default_quantization: str, quality_profile: Optional[str]) -> str:
    if quality_profile is None:
        return default_quantization
    profile_map = {
        "fast": "int8",
        "balanced": "float16",
        "precise": "float32",
    }
    return profile_map.get(quality_profile, default_quantization)


def transcribe_job(
    audio_key: str,
    *,
    language: Optional[str] = None,
    profile_id: Optional[int] = None,
    user_id: Optional[int] = None,
    quality_profile: Optional[str] = None,
) -> dict:
    """Worker entrypoint that downloads audio, runs transcription, and uploads results."""

    settings = get_settings()
    storage_client = S3StorageClient()
    quantization = _select_quantization(settings.transcription_quantization, quality_profile)
    transcription_service = TranscriptionService(quantization=quantization)

    storage_client.ensure_buckets()

    job = get_current_job()
    if job is not None:
        _update_job_meta({"status": "transcribing", "quality_profile": quality_profile})

    with session_scope() as session:
        if job is not None and user_id is not None:
            transcript = session.query(Transcript).filter(Transcript.job_id == job.id).one_or_none()
            if transcript:
                transcript.status = "transcribing"
                transcript.language = language or transcript.language
                transcript.quality_profile = quality_profile or transcript.quality_profile
                transcript.updated_at = datetime.utcnow()

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = Path(tmpdir) / Path(audio_key).name
        storage_client.download_audio(audio_key, audio_path)

        transcript_parts: list[str] = []

        def on_token(token: dict) -> None:
            transcript_parts.append(token["text"])
            segment_index = int(token.get("segment", len(transcript_parts)))
            _update_job_meta(
                {
                    "last_token": json.dumps(token),
                    "progress": len(transcript_parts),
                    "segment": segment_index,
                }
            )

        result = transcription_service.transcribe(audio_path, token_callback=on_token, language=language)

    transcript_key = f"{audio_key}.txt"
    storage_client.upload_transcript(result["text"], transcript_key)

    _update_job_meta(
        {
            "status": "completed",
            "transcript_key": transcript_key,
            "segments": result["segments"],
            "language": result["language"],
            "duration": result.get("duration"),
            "segment": len(result.get("segments", [])),
        }
    )

    with session_scope() as session:
        if job is not None:
            transcript = session.query(Transcript).filter(Transcript.job_id == job.id).one_or_none()
            if transcript:
                transcript.status = "completed"
                transcript.transcript_key = transcript_key
                transcript.language = result["language"]
                transcript.duration_seconds = result.get("duration")
                transcript.segments = json.dumps(result.get("segments", []))
                transcript.completed_at = datetime.utcnow()
                transcript.updated_at = transcript.completed_at

    logger.info(
        "Transcription job completed",
        extra={
            "audio_key": audio_key,
            "transcript_key": transcript_key,
            "profile_id": profile_id,
            "user_id": user_id,
        },
    )

    return {"transcript_key": transcript_key, **result}
