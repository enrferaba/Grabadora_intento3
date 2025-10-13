"""Utility for interacting with S3/MinIO storage."""
from __future__ import annotations

import io
import logging
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import BinaryIO, Dict, List, Optional, Tuple

try:  # pragma: no cover - optional dependency
    import boto3
    from botocore.exceptions import ClientError, EndpointConnectionError
except ImportError:  # pragma: no cover - optional dependency
    boto3 = None  # type: ignore

    class ClientError(Exception):
        pass

    class EndpointConnectionError(Exception):
        pass

from app.config import get_settings

logger = logging.getLogger(__name__)


class S3StorageClient:
    """Simplified wrapper for boto3 clients used by the application."""

    _memory_buckets: Dict[str, Dict[str, bytes]] = {}
    _bucket_state: Dict[Tuple[str, str, str], bool] = {}
    _bucket_lock = Lock()

    def __init__(self) -> None:
        settings = get_settings()
        self.audio_bucket = settings.s3_bucket_audio
        self.transcripts_bucket = settings.s3_bucket_transcripts
        self._endpoint_url = settings.s3_endpoint_url
        self._presigned_ttl = settings.s3_presigned_ttl
        self._local_root = Path(settings.storage_dir)
        self._local_audio_dir = self._local_root / settings.audio_cache_dir
        self._local_transcripts_dir = self._local_root / settings.transcripts_dir
        self._local_mode = False
        self._client = None

        if boto3 is None:  # pragma: no cover - dependency not installed
            self._activate_local_mode()
        else:
            self._client = boto3.client(
                "s3",
                endpoint_url=settings.s3_endpoint_url,
                region_name=settings.s3_region_name,
                aws_access_key_id=settings.s3_access_key,
                aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
            )

    def _activate_local_mode(self, error: Optional[Exception] = None) -> None:
        if not self._local_mode:
            if error is not None:
                logger.warning(
                    "Falling back to local disk storage because the S3 endpoint is unavailable.",
                    extra={"endpoint": self._endpoint_url, "error": repr(error)},
                )
            self._local_mode = True
            self._ensure_local_dirs()
        with self._bucket_lock:
            self._bucket_state.clear()
        self._client = None

    def _ensure_local_dirs(self) -> None:
        self._local_audio_dir.mkdir(parents=True, exist_ok=True)
        self._local_transcripts_dir.mkdir(parents=True, exist_ok=True)

    def _local_path(self, base: Path, object_name: str) -> Path:
        relative = Path(object_name)
        target = base.joinpath(*relative.parts)
        resolved_base = base.resolve()
        resolved_target = target.resolve()
        if not resolved_target.is_relative_to(resolved_base):  # type: ignore[attr-defined]
            raise ValueError(f"Ruta fuera del directorio de almacenamiento: {object_name}")
        resolved_target.parent.mkdir(parents=True, exist_ok=True)
        return resolved_target

    def _ensure_memory_bucket(self, bucket: str) -> Dict[str, bytes]:
        bucket_store = self._memory_buckets.setdefault(bucket, {})
        return bucket_store

    def _fallback_to_memory(self, error: Optional[Exception] = None) -> None:
        # legacy in-memory fallback kept for backwards compatibility in tests
        self._activate_local_mode(error)
        self._ensure_memory_bucket(self.audio_bucket)
        self._ensure_memory_bucket(self.transcripts_bucket)

    def _rewind(self, fileobj: BinaryIO) -> None:
        try:
            fileobj.seek(0, io.SEEK_SET)  # type: ignore[attr-defined]
        except (AttributeError, OSError, io.UnsupportedOperation):
            pass

    def ensure_buckets(self) -> None:
        cache_key = (self.audio_bucket, self.transcripts_bucket, self._endpoint_url or "local")
        with self._bucket_lock:
            if self._bucket_state.get(cache_key):
                if self._local_mode:
                    self._ensure_local_dirs()
                elif self._client is None:
                    self._ensure_memory_bucket(self.audio_bucket)
                    self._ensure_memory_bucket(self.transcripts_bucket)
                return
        if self._client is None:
            if self._local_mode:
                self._ensure_local_dirs()
            else:
                self._ensure_memory_bucket(self.audio_bucket)
                self._ensure_memory_bucket(self.transcripts_bucket)
            with self._bucket_lock:
                self._bucket_state[cache_key] = True
            return
        for bucket in {self.audio_bucket, self.transcripts_bucket}:
            try:
                self._client.head_bucket(Bucket=bucket)
            except ClientError:
                logger.info("Creating bucket", extra={"bucket": bucket})
                try:
                    self._client.create_bucket(Bucket=bucket)
                except EndpointConnectionError as exc:  # pragma: no cover - network failure
                    self._activate_local_mode(exc)
                    return
            except EndpointConnectionError as exc:  # pragma: no cover - network failure
                self._activate_local_mode(exc)
                return
        with self._bucket_lock:
            self._bucket_state[cache_key] = True

    def upload_audio(self, fileobj: BinaryIO, object_name: str) -> str:
        self._rewind(fileobj)
        if self._local_mode:
            destination = self._local_path(self._local_audio_dir, object_name)
            with open(destination, "wb") as handle:
                handle.write(fileobj.read())
            return object_name
        if self._client is None:
            data = fileobj.read()
            store = self._ensure_memory_bucket(self.audio_bucket)
            store[object_name] = data
            return object_name
        self._rewind(fileobj)
        self._client.upload_fileobj(fileobj, self.audio_bucket, object_name)
        return object_name

    def upload_transcript(self, transcript: str, object_name: str) -> str:
        if self._local_mode:
            destination = self._local_path(self._local_transcripts_dir, object_name)
            destination.write_text(transcript, encoding="utf-8")
            return object_name
        if self._client is None:
            store = self._ensure_memory_bucket(self.transcripts_bucket)
            store[object_name] = transcript.encode("utf-8")
            return object_name
        data = transcript.encode("utf-8")
        stream = io.BytesIO(data)
        self._client.upload_fileobj(stream, self.transcripts_bucket, object_name)
        return object_name

    def download_audio(self, object_name: str, destination: Path) -> None:
        if self._local_mode:
            source = self._local_path(self._local_audio_dir, object_name)
            if not source.exists():
                raise FileNotFoundError(object_name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
            return
        if self._client is None:
            store = self._ensure_memory_bucket(self.audio_bucket)
            if object_name not in store:
                raise FileNotFoundError(object_name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(store[object_name])
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        with open(destination, "wb") as file_obj:
            self._client.download_fileobj(self.audio_bucket, object_name, file_obj)

    def download_transcript(self, object_name: str) -> Optional[str]:
        if self._local_mode:
            source = self._local_path(self._local_transcripts_dir, object_name)
            if not source.exists():
                return None
            return source.read_text(encoding="utf-8")
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

    def delete_audio(self, object_name: str) -> None:
        """Remove an audio blob from the configured backend."""

        if self._local_mode:
            target = self._local_path(self._local_audio_dir, object_name)
            if target.exists():
                target.unlink()
            return
        if self._client is None:
            store = self._ensure_memory_bucket(self.audio_bucket)
            store.pop(object_name, None)
            return
        try:
            self._client.delete_object(Bucket=self.audio_bucket, Key=object_name)
        except ClientError as exc:
            code = getattr(getattr(exc, "response", {}), "get", lambda *_: None)("Error", {}).get("Code")  # type: ignore[arg-type]
            if code not in {"NoSuchKey", "404"}:
                raise

    def delete_transcript(self, object_name: str) -> None:
        """Remove a transcript artifact regardless of the storage backend."""

        if self._local_mode:
            target = self._local_path(self._local_transcripts_dir, object_name)
            if target.exists():
                target.unlink()
            return
        if self._client is None:
            store = self._ensure_memory_bucket(self.transcripts_bucket)
            store.pop(object_name, None)
            return
        try:
            self._client.delete_object(Bucket=self.transcripts_bucket, Key=object_name)
        except ClientError as exc:
            code = getattr(getattr(exc, "response", {}), "get", lambda *_: None)("Error", {}).get("Code")  # type: ignore[arg-type]
            if code not in {"NoSuchKey", "404"}:
                raise

    def list_transcripts(self, prefix: Optional[str] = None) -> List[dict]:
        if self._local_mode:
            items: List[dict] = []
            for path in self._local_transcripts_dir.rglob("*"):
                if not path.is_file():
                    continue
                relative = path.relative_to(self._local_transcripts_dir).as_posix()
                if prefix and not relative.startswith(prefix):
                    continue
                stat = path.stat()
                items.append({
                    "key": relative,
                    "size": stat.st_size,
                    "last_modified": datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                })
            return items
        if self._client is None:
            store = self._ensure_memory_bucket(self.transcripts_bucket)
            items = []
            for key, payload in store.items():
                if prefix and not key.startswith(prefix):
                    continue
                items.append({
                    "key": key,
                    "size": len(payload),
                    "last_modified": datetime.now(UTC),
                })
            return items
        paginator = self._client.get_paginator("list_objects_v2")
        operation_parameters = {"Bucket": self.transcripts_bucket}
        if prefix:
            operation_parameters["Prefix"] = prefix
        items: List[dict] = []
        for page in paginator.paginate(**operation_parameters):
            for obj in page.get("Contents", []):
                items.append({
                    "key": obj["Key"],
                    "size": obj.get("Size", 0),
                    "last_modified": obj.get("LastModified"),
                })
        return items

    def create_presigned_url(self, object_name: str, expires_in: Optional[int] = None) -> Optional[str]:
        ttl = expires_in or self._presigned_ttl
        if self._local_mode:
            path = self._local_path(self._local_transcripts_dir, object_name)
            if not path.exists():
                return None
            return path.resolve().as_uri()
        if self._client is None:
            store = self._ensure_memory_bucket(self.transcripts_bucket)
            if object_name not in store:
                return None
            return f"memory://{self.transcripts_bucket}/{object_name}?ttl={ttl}"
        try:
            return self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.transcripts_bucket, "Key": object_name},
                ExpiresIn=ttl,
            )
        except ClientError:
            logger.exception("Unable to generate presigned URL", extra={"key": object_name})
            return None
