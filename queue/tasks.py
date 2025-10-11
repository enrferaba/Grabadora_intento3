"""RQ tasks responsible for executing transcription workloads."""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Optional
try:  # pragma: no cover - optional dependency
    from rq import get_current_job
except ImportError:  # pragma: no cover
    def get_current_job():  # type: ignore
        return None

from app.config import get_settings
from services.transcription import TranscriptionService
from storage.s3 import S3StorageClient

logger = logging.getLogger(__name__)


def _update_job_meta(meta: dict) -> None:
    job = get_current_job()
    if job is None:
        return
    job.meta.update(meta)
    job.save_meta()


def transcribe_job(
    audio_key: str,
    *,
    language: Optional[str] = None,
    profile_id: Optional[int] = None,
) -> dict:
    """Worker entrypoint that downloads audio, runs transcription, and uploads results."""

    settings = get_settings()
    storage_client = S3StorageClient()
    transcription_service = TranscriptionService(quantization=settings.transcription_quantization)

    storage_client.ensure_buckets()

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = Path(tmpdir) / Path(audio_key).name
        storage_client.download_audio(audio_key, audio_path)

        transcript_parts: list[str] = []

        def on_token(token: str) -> None:
            transcript_parts.append(token)
            _update_job_meta({"last_token": token, "progress": len(transcript_parts)})

        _update_job_meta({"status": "transcribing"})
        result = transcription_service.transcribe(audio_path, token_callback=on_token, language=language)

    transcript_key = f"{audio_key}.txt"
    storage_client.upload_transcript(result["text"], transcript_key)

    _update_job_meta({
        "status": "completed",
        "transcript_key": transcript_key,
        "segments": result["segments"],
        "language": result["language"],
    })

    logger.info(
        "Transcription job completed",
        extra={
            "audio_key": audio_key,
            "transcript_key": transcript_key,
            "profile_id": profile_id,
        },
    )

    return {"transcript_key": transcript_key, **result}
