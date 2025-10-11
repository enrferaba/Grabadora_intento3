from __future__ import annotations

from types import SimpleNamespace

from storage.s3 import S3StorageClient


class DummyClient:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, str]] = []

    def upload_fileobj(self, fileobj, bucket: str, key: str) -> None:
        data = fileobj.read()
        self.uploads.append((bucket, key, data))

    def head_bucket(self, Bucket: str) -> None:  # noqa: N803
        pass

    def create_bucket(self, Bucket: str) -> None:  # noqa: N803
        self.uploads.append(("create", Bucket, b""))


def test_upload_transcript(monkeypatch):
    client = DummyClient()
    monkeypatch.setattr("storage.s3.boto3", SimpleNamespace(client=lambda *args, **kwargs: client))

    storage = S3StorageClient()
    storage.ensure_buckets()
    storage.upload_transcript("hello", "t.txt")

    assert (storage.transcripts_bucket, "t.txt", b"hello") in client.uploads
