from __future__ import annotations

from types import SimpleNamespace

import pytest

from taskqueue import tasks


class DummyStorage:
    def __init__(self) -> None:
        self.audio = {}
        self.transcripts = {}

    def ensure_buckets(self) -> None:
        pass

    def download_audio(self, key, destination):
        destination.write_text("audio")

    def upload_transcript(self, text, key):
        self.transcripts[key] = text


class DummyTranscriber:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def transcribe(self, path, token_callback=None, language=None):
        if token_callback:
            token_callback("Hello")
            token_callback(" ")
        return {
            "text": "Hello world",
            "segments": [
                {"start": 0, "end": 1, "text": "Hello world"}
            ],
            "language": language or "en",
            "duration": 1.0,
        }


class DummyJob:
    def __init__(self) -> None:
        self.meta = {}

    def save_meta(self) -> None:
        pass


@pytest.fixture(autouse=True)
def patch_dependencies(monkeypatch):
    monkeypatch.setattr("taskqueue.tasks.S3StorageClient", lambda: DummyStorage())
    monkeypatch.setattr("taskqueue.tasks.TranscriptionService", lambda **kwargs: DummyTranscriber())
    job = DummyJob()
    monkeypatch.setattr("taskqueue.tasks.get_current_job", lambda: job)
    yield job


def test_transcribe_job_updates_meta_and_returns_payload(patch_dependencies):
    result = tasks.transcribe_job("audio-key", language="en")

    assert result["text"] == "Hello world"
    assert patch_dependencies.meta["status"] == "completed"
