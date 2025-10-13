"""Application configuration with a lightweight settings loader.

This module intentionally avoids heavy optional dependencies so that the
project remains usable in constrained execution environments (like the
exercise runner). Environment variables using the ``GRABADORA_`` prefix can
override the defaults defined below.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, fields
from functools import lru_cache
from typing import Any, Literal, get_args, get_origin


def _coerce(value: str, annotation: Any) -> Any:
    """Best-effort coercion of environment variable values."""

    origin = get_origin(annotation)
    if origin is Literal:
        # literals are strings in our settings; trust the env override.
        return value

    if annotation in (str, Any):
        return value
    if annotation in (int, float):
        return annotation(value)
    if annotation is bool:
        return value.lower() in {"1", "true", "yes", "on"}

    if origin is list and get_args(annotation):  # pragma: no cover - unused today
        subtype = get_args(annotation)[0]
        return [
            _coerce(item.strip(), subtype)
            for item in value.split(",")
            if item.strip()
        ]

    return value


@dataclass
class Settings:
    """Central configuration for the transcription platform."""

    api_title: str = "Grabadora"
    api_version: str = "0.1.0"
    api_description: str = (
        "Streaming transcription service with queue, storage, and metrics."
    )
    app_name: str = "Grabadora"

    redis_url: str = "redis://redis:6379/0"
    rq_default_queue: str = "transcription"
    rq_job_timeout: int = 1800
    rq_result_ttl: int = 86400
    rq_failure_ttl: int = 3600
    queue_backend: Literal["auto", "redis", "memory"] = "auto"

    database_url: str = (
        "postgresql+psycopg2://postgres:postgres@db:5432/grabadora"
    )

    s3_endpoint_url: str = "http://minio:9000"
    s3_region_name: str = "us-east-1"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket_audio: str = "audio"
    s3_bucket_transcripts: str = "transcripts"
    s3_presigned_ttl: int = 86400

    storage_dir: str = "storage"
    transcripts_dir: str = "transcripts"
    audio_cache_dir: str = "audio-cache"
    models_cache_dir: str = "models"
    frontend_origin: str | None = None
    frontend_origin_regex: str | None = None

    max_upload_size_mb: int = 500
    live_window_seconds: float = 5.0
    live_window_overlap_seconds: float = 1.0
    live_repeat_window_seconds: float = 2.0
    live_repeat_max_duplicates: int = 3

    huggingface_token: str | None = None
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str | None = None

    enable_dummy_transcriber: bool = False
    whisper_model_size: str = "large-v2"
    whisper_device: str = "cuda"
    whisper_compute_type: str = "float16"
    whisper_language: str | None = None
    whisper_use_faster: bool = True
    whisper_enable_speaker_diarization: bool = False
    whisper_batch_size: int = 4
    whisper_condition_on_previous_text: bool = True
    whisper_word_timestamps: bool = True
    whisper_vad_mode: str = "auto"
    whisper_vad_repo_id: str = "pyannote/segmentation"
    whisper_vad_filename: str = "pytorch_model.bin"
    whisper_force_cuda: bool = False
    whisper_compression_ratio_threshold: float = 2.4
    whisper_log_prob_threshold: float = -1.0
    whisper_final_beam: int = 1
    whisper_live_beam: int = 1

    debug_event_limit: int = 500

    jwt_secret_key: str = "super-secret"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 30

    transcription_quantization: Literal["float32", "float16", "int8"] = "float16"

    prometheus_namespace: str = "grabadora"

    _env_prefix: str = "GRABADORA_"

    def __post_init__(self) -> None:
        for field in fields(self):
            if field.name.startswith("_"):
                continue
            env_name = f"{self._env_prefix}{field.name.upper()}"
            raw_value = os.getenv(env_name)
            if raw_value is None:
                raw_value = os.getenv(field.name.upper())
            if raw_value is None:
                continue
            try:
                value = _coerce(raw_value, field.type)
            except Exception:
                # fall back to the raw string if coercion fails.
                value = raw_value
            setattr(self, field.name, value)


@lru_cache()
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance."""

    return Settings()


# Backwards compatibility alias for code that expects a module-level ``settings``.
settings = get_settings()
