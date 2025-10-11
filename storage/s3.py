"""Utility for interacting with S3/MinIO storage."""
from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import BinaryIO, Optional

try:  # pragma: no cover - optional dependency
    import boto3
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover - optional dependency
    boto3 = None  # type: ignore

    class ClientError(Exception):
        pass

from app.config import get_settings

logger = logging.getLogger(__name__)


class S3StorageClient:
    """Simplified wrapper for boto3 clients used by the application."""

    def __init__(self) -> None:
        settings = get_settings()
        if boto3 is None:  # pragma: no cover - dependency not installed
            raise RuntimeError("boto3 is required for S3StorageClient")
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region_name,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
        )
        self.audio_bucket = settings.s3_bucket_audio
        self.transcripts_bucket = settings.s3_bucket_transcripts

    def ensure_buckets(self) -> None:
        for bucket in {self.audio_bucket, self.transcripts_bucket}:
            try:
                self._client.head_bucket(Bucket=bucket)
            except ClientError:
                logger.info("Creating bucket", extra={"bucket": bucket})
                self._client.create_bucket(Bucket=bucket)

    def upload_audio(self, fileobj: BinaryIO, object_name: str) -> str:
        self._client.upload_fileobj(fileobj, self.audio_bucket, object_name)
        return object_name

    def upload_transcript(self, transcript: str, object_name: str) -> str:
        data = transcript.encode("utf-8")
        stream = io.BytesIO(data)
        self._client.upload_fileobj(stream, self.transcripts_bucket, object_name)
        return object_name

    def download_audio(self, object_name: str, destination: Path) -> None:
        with open(destination, "wb") as file_obj:
            self._client.download_fileobj(self.audio_bucket, object_name, file_obj)

    def download_transcript(self, object_name: str) -> Optional[str]:
        try:
            response = self._client.get_object(Bucket=self.transcripts_bucket, Key=object_name)
        except ClientError as exc:
            if exc.response["Error"].get("Code") == "NoSuchKey":
                return None
            raise
        body = response["Body"].read()
        return body.decode("utf-8")
