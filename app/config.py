"""Application configuration using Pydantic settings."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """Central configuration for the transcription platform."""

    api_title: str = Field("Grabadora", description="API title exposed by FastAPI.")
    api_version: str = Field("0.1.0", description="Semantic version of the API.")
    api_description: str = Field(
        "Streaming transcription service with queue, storage, and metrics.",
        description="Metadata description used by the OpenAPI schema.",
    )

    redis_url: str = Field("redis://redis:6379/0", description="Redis connection URL.")
    rq_default_queue: str = Field("transcription", description="Name of the default RQ queue.")

    database_url: str = Field(
        "postgresql+psycopg2://postgres:postgres@db:5432/grabadora",
        description="SQLAlchemy-compatible database URL for PostgreSQL/MariaDB.",
    )

    s3_endpoint_url: str = Field("http://minio:9000", description="Endpoint for S3/MinIO service.")
    s3_region_name: str = Field("us-east-1", description="Region name for S3-compatible services.")
    s3_access_key: str = Field("minioadmin", description="S3 access key.")
    s3_secret_key: str = Field("minioadmin", description="S3 secret key.")
    s3_bucket_audio: str = Field("audio", description="Bucket used to store uploaded audio files.")
    s3_bucket_transcripts: str = Field("transcripts", description="Bucket used to store final transcript payloads.")

    jwt_secret_key: str = Field("super-secret", description="Secret used to sign JWT tokens.")
    jwt_algorithm: str = Field("HS256", description="Algorithm used to sign JWT tokens.")
    jwt_expiration_minutes: int = Field(30, description="Default JWT expiration window in minutes.")

    transcription_quantization: Literal["float32", "float16", "int8"] = Field(
        "float16",
        description="Default quantization level used by faster-whisper.",
    )

    prometheus_namespace: str = Field("grabadora", description="Prometheus metric namespace.")

    class Config:
        env_prefix = "GRABADORA_"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()
