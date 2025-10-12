from pathlib import Path
from types import SimpleNamespace

from pathlib import Path
from types import SimpleNamespace

import pytest

from services.transcription import TranscriptionService


class DummyToken:
    def __init__(self, text: str) -> None:
        self.text = text


class DummySegment:
    def __init__(self, text: str, start: float = 0.0, end: float = 1.0) -> None:
        self.text = text
        self.start = start
        self.end = end
        self.tokens = [DummyToken(char) for char in text]


class DummyModel:
    def __init__(self, *args, **kwargs) -> None:
        self.calls = [(args, kwargs)]

    def transcribe(self, path: str, language: str | None = None):
        segments = [DummySegment("Hi", 0.0, 0.5), DummySegment("!", 0.5, 0.75)]
        info = SimpleNamespace(duration=1.0, language=language or "en")
        return segments, info


def test_transcription_streams_delta_tokens(monkeypatch):
    service = TranscriptionService(quantization="float16", model_factory=lambda *args, **kwargs: DummyModel(*args, **kwargs))

    tokens: list[dict] = []
    result = service.transcribe(Path("dummy.wav"), token_callback=tokens.append)

    assert "Hi!" == result["text"]
    assert tokens == [
        {"text": "H", "t0": 0.0, "t1": 0.5, "segment": 0},
        {"text": "i", "t0": 0.0, "t1": 0.5, "segment": 0},
        {"text": "!", "t0": 0.5, "t1": 0.75, "segment": 1},
    ]


def test_invalid_quantization():
    with pytest.raises(ValueError):
        TranscriptionService(quantization="invalid")


def test_simulated_transcription_when_model_missing(tmp_path):
    audio_path = tmp_path / "demo.wav"
    audio_path.write_bytes(b"fake audio payload")

    service = TranscriptionService()

    collected: list[dict] = []
    result = service.transcribe(audio_path, token_callback=collected.append)

    assert "Transcripción simulada" in result["text"]
    assert result["segments"][0]["text"].startswith("Transcripción simulada")
    assert collected, "expected simulated tokens to be emitted"
