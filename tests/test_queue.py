import json

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
            token_callback({"text": "Hello", "t0": 0.0, "t1": 1.0, "segment": 0})
            token_callback({"text": " ", "t0": 1.0, "t1": 2.0, "segment": 1})
        return {
            "text": "Hello world",
            "segments": [{"start": 0, "end": 1, "text": "Hello world"}],
            "language": language or "en",
            "duration": 1.0,
        }


class DummyJob:
    def __init__(self) -> None:
        self.id = "dummy"
        self.meta = {}

    def save_meta(self) -> None:
        pass


@pytest.fixture(autouse=True)
def patch_dependencies(monkeypatch):
    monkeypatch.setattr("taskqueue.tasks.S3StorageClient", lambda: DummyStorage())
    monkeypatch.setattr(
        "taskqueue.tasks.TranscriptionService", lambda **kwargs: DummyTranscriber()
    )
    job = DummyJob()
    monkeypatch.setattr("taskqueue.tasks.get_current_job", lambda: job)

    class DummyQuery:
        def __init__(self) -> None:
            self._value = None

        def filter(self, *args, **kwargs):
            return self

        def one_or_none(self):
            return None

        def order_by(self, *args, **kwargs):
            return self

        def all(self):
            return []

    class DummySession:
        def query(self, *args, **kwargs):
            return DummyQuery()

        def add(self, *args, **kwargs):
            pass

        def flush(self):
            pass

    class DummySessionScope:
        def __call__(self):
            return self

        def __enter__(self):
            return DummySession()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("taskqueue.tasks.session_scope", DummySessionScope())
    yield job


def test_transcribe_job_updates_meta_and_returns_payload(patch_dependencies):
    result = tasks.transcribe_job("audio-key", language="en", quality_profile="fast")

    assert result["text"] == "Hello world"
    assert patch_dependencies.meta["status"] == "completed"
    assert json.loads(patch_dependencies.meta["last_token"]) == {
        "text": " ",
        "t0": 1.0,
        "t1": 2.0,
        "segment": 1,
    }
