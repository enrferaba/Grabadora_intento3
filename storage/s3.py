"""Utility for interacting with S3/MinIO storage."""
from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import BinaryIO, Dict, Optional

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

    _memory_buckets: Dict[str, Dict[str, bytes]] = {}

    def __init__(self) -> None:
        settings = get_settings()
        self.audio_bucket = settings.s3_bucket_audio
        self.transcripts_bucket = settings.s3_bucket_transcripts
        if boto3 is None:  # pragma: no cover - dependency not installed
            self._client = None
        else:
            self._client = boto3.client(
                "s3",
                endpoint_url=settings.s3_endpoint_url,
                region_name=settings.s3_region_name,
                aws_access_key_id=settings.s3_access_key,
                aws_secret_access_key=settings.s3_secret_key,
            )

    def _ensure_memory_bucket(self, bucket: str) -> Dict[str, bytes]:
        bucket_store = self._memory_buckets.setdefault(bucket, {})
        return bucket_store

    def ensure_buckets(self) -> None:
        if self._client is None:
            self._ensure_memory_bucket(self.audio_bucket)
            self._ensure_memory_bucket(self.transcripts_bucket)
            return
        for bucket in {self.audio_bucket, self.transcripts_bucket}:
            try:
                self._client.head_bucket(Bucket=bucket)
            except ClientError:
                logger.info("Creating bucket", extra={"bucket": bucket})
                self._client.create_bucket(Bucket=bucket)

    def upload_audio(self, fileobj: BinaryIO, object_name: str) -> str:
        if self._client is None:
            data = fileobj.read()
            store = self._ensure_memory_bucket(self.audio_bucket)
            store[object_name] = data
            return object_name
        self._client.upload_fileobj(fileobj, self.audio_bucket, object_name)
        return object_name

    def upload_transcript(self, transcript: str, object_name: str) -> str:
        if self._client is None:
            store = self._ensure_memory_bucket(self.transcripts_bucket)
            store[object_name] = transcript.encode("utf-8")
            return object_name
        data = transcript.encode("utf-8")
        stream = io.BytesIO(data)
        self._client.upload_fileobj(stream, self.transcripts_bucket, object_name)
        return object_name

    def download_audio(self, object_name: str, destination: Path) -> None:
        if self._client is None:
            store = self._ensure_memory_bucket(self.audio_bucket)
            if object_name not in store:
                raise FileNotFoundError(object_name)
            destination.write_bytes(store[object_name])
            return
        with open(destination, "wb") as file_obj:
            self._client.download_fileobj(self.audio_bucket, object_name, file_obj)

    def download_transcript(self, object_name: str) -> Optional[str]:
        if self._client is None:
            store = self._ensure_memory_bucket(self.transcripts_bucket)
            data = store.get(object_name)
            if data is None:
                return None
            return data.decode("utf-8")
        try:
            response = self._client.get_object(Bucket=self.transcripts_bucket, Key=object_name)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "NoSuchKey":
                return None
            raise
        body = response["Body"].read()
        return body.decode("utf-8")
