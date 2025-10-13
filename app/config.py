"""Application configuration handled with Pydantic models."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Literal

from dotenv import dotenv_values
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, SecretStr

ENV_PREFIX = "GRABADORA_"


def _collect_env(prefix: str = ENV_PREFIX) -> dict[str, Any]:
    """Load .env + OS variables and normalise keys."""

    raw: dict[str, Any] = {}
    sources = [dotenv_values(".env"), os.environ]
    for source in sources:
        for key, value in source.items():
            if value in (None, ""):
                continue
            key_upper = key.upper()
            if key_upper.startswith(prefix):
                stripped = key_upper[len(prefix) :]
            else:
                stripped = key_upper
            raw[stripped] = value
            raw[stripped.lower()] = value
    return raw


class Settings(BaseModel):
    """Central configuration for the transcription platform."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True, validate_assignment=False)

    api_title: str = Field(default="Grabadora")
    api_version: str = Field(default="0.1.0")
    api_description: str = Field(
        default="Streaming transcription service with queue, storage, and metrics.",
    )
    app_name: str = Field(default="Grabadora")

    app_env: Literal["development", "staging", "production", "test"] = Field(
        default="development",
        validation_alias=AliasChoices("APP_ENV", "ENVIRONMENT"),
    )
    log_level: str = Field(
        default="INFO",
        validation_alias=AliasChoices("LOG_LEVEL"),
    )
    gpu_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("GPU_ENABLED"),
    )

    redis_url: str = Field(default="redis://redis:6379/0")
    rq_default_queue: str = Field(default="transcription")
    rq_job_timeout: int = Field(default=1800)
    rq_result_ttl: int = Field(default=86400)
    rq_failure_ttl: int = Field(default=3600)
    queue_backend: Literal["auto", "redis", "memory"] = Field(default="auto")

    database_url: str = Field(
        default="postgresql+psycopg2://postgres:postgres@db:5432/grabadora",
        validation_alias=AliasChoices("DATABASE_URL"),
    )

    s3_endpoint_url: str = Field(
        default="http://minio:9000",
        validation_alias=AliasChoices("S3_ENDPOINT", "S3_ENDPOINT_URL"),
    )
    s3_region_name: str = Field(default="us-east-1")
    s3_access_key: str = Field(
        default="minioadmin",
        min_length=1,
        validation_alias=AliasChoices("S3_ACCESS_KEY"),
    )
    s3_secret_key: SecretStr = Field(
        default=SecretStr("minioadmin"),
        validation_alias=AliasChoices("S3_SECRET_KEY"),
    )
    s3_bucket_audio: str = Field(
        default="audio",
        min_length=1,
        validation_alias=AliasChoices("S3_BUCKET_AUDIO", "S3_BUCKET"),
    )
    s3_bucket_transcripts: str = Field(
        default="transcripts",
        min_length=1,
        validation_alias=AliasChoices("S3_BUCKET_TRANSCRIPTS"),
    )
    s3_presigned_ttl: int = Field(default=86400, ge=60)

    storage_dir: str = Field(default="storage")
    transcripts_dir: str = Field(default="transcripts")
    audio_cache_dir: str = Field(default="audio-cache")
    models_cache_dir: str = Field(default="models")
    frontend_origin: str | None = Field(default=None)
    frontend_origin_regex: str | None = Field(default=None)

    max_upload_size_mb: int = Field(default=500, ge=1)
    live_window_seconds: float = Field(default=5.0, gt=0)
    live_window_overlap_seconds: float = Field(default=1.0, ge=0)
    live_repeat_window_seconds: float = Field(default=2.0, ge=0)
    live_repeat_max_duplicates: int = Field(default=3, ge=0)

    huggingface_token: str | None = Field(default=None)
    google_client_id: str | None = Field(default=None)
    google_client_secret: str | None = Field(default=None)
    google_redirect_uri: str | None = Field(default=None)

    enable_dummy_transcriber: bool = Field(default=False)
    whisper_model_size: str = Field(
        default="large-v2",
        validation_alias=AliasChoices("ASR_MODEL", "WHISPER_MODEL_SIZE"),
    )
    whisper_device: str = Field(default="cuda")
    whisper_compute_type: str = Field(default="float16")
    whisper_language: str | None = Field(default=None)
    whisper_use_faster: bool = Field(default=True)
    whisper_enable_speaker_diarization: bool = Field(default=False)
    whisper_batch_size: int = Field(default=4, ge=1)
    whisper_condition_on_previous_text: bool = Field(default=True)
    whisper_word_timestamps: bool = Field(default=True)
    whisper_vad_mode: str = Field(default="auto")
    whisper_vad_repo_id: str = Field(default="pyannote/segmentation")
    whisper_vad_filename: str = Field(default="pytorch_model.bin")
    whisper_force_cuda: bool = Field(default=False)
    whisper_compression_ratio_threshold: float = Field(default=2.4)
    whisper_log_prob_threshold: float = Field(default=-1.0)
    whisper_final_beam: int = Field(default=1, ge=1)
    whisper_live_beam: int = Field(default=1, ge=1)

    debug_event_limit: int = Field(default=500, ge=1)

    jwt_secret_key: SecretStr = Field(
        default=SecretStr("local-dev-secret"),
        validation_alias=AliasChoices("JWT_SECRET", "JWT_SECRET_KEY"),
    )
    jwt_algorithm: str = Field(default="HS256")
    jwt_expiration_minutes: int = Field(default=30, ge=1)

    transcription_quantization: Literal["float32", "float16", "int8"] = Field(
        default="float16",
        validation_alias=AliasChoices("TRANSCRIPTION_QUANTIZATION"),
    )

    prometheus_namespace: str = Field(default="grabadora")

    @property
    def jwt_secret(self) -> str:
        """Return the decrypted JWT secret string."""

        return self.jwt_secret_key.get_secret_value()

    @classmethod
    def load(cls) -> "Settings":
        data = _collect_env()
        instance = cls.model_validate(data)
        _validate_required_settings(instance)
        return instance


@lru_cache()
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance."""

    return Settings.load()


def _validate_required_settings(settings: Settings) -> None:
    """Fail fast when essential secrets are missing or placeholders."""

    missing: dict[str, Any] = {}
    if settings.jwt_secret_key.get_secret_value() in {
        "",
        "change-me",
        "super-secret",
        "please-change-this-secret",
    }:
        missing["GRABADORA_JWT_SECRET_KEY"] = "Define un secreto fuerte para JWT."
    for bucket_key in (settings.s3_bucket_audio, settings.s3_bucket_transcripts):
        if not bucket_key.strip():
            missing["GRABADORA_S3_BUCKET_*"] = "Los buckets de audio y transcripciones no pueden estar vacíos."
    if missing:
        details = "; ".join(f"{key}: {reason}" for key, reason in missing.items())
        raise ValueError(f"Configuración incompleta: {details}")


# Backwards compatibility alias for code that expects a module-level ``settings``.
settings = get_settings()
