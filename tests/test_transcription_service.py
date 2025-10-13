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


@pytest.fixture
def fake_settings(monkeypatch, tmp_path):
    def _factory(**overrides):
        base = SimpleNamespace(
            whisper_model_size="large-v2",
            whisper_device="cpu",
            whisper_compute_type="float16",
            transcription_quantization="float16",
            models_cache_dir=str(tmp_path / "models"),
            huggingface_token=None,
        )
        for key, value in overrides.items():
            setattr(base, key, value)
        monkeypatch.setattr("services.transcription.get_settings", lambda: base)
        return base

    return _factory


def test_transcription_streams_delta_tokens(fake_settings):
    fake_settings()
    service = TranscriptionService(
        quantization="float16",
        model_factory=lambda *args, **kwargs: DummyModel(*args, **kwargs),
    )

    tokens: list[dict] = []
    result = service.transcribe(Path("dummy.wav"), token_callback=tokens.append)

    assert "Hi!" == result["text"]
    assert tokens == [
        {"text": "H", "t0": 0.0, "t1": 0.5, "segment": 0},
        {"text": "i", "t0": 0.0, "t1": 0.5, "segment": 0},
        {"text": "!", "t0": 0.5, "t1": 0.75, "segment": 1},
    ]


def test_invalid_quantization(fake_settings):
    fake_settings(whisper_compute_type="")
    with pytest.raises(ValueError):
        TranscriptionService(quantization="invalid")


def test_simulated_transcription_when_model_missing(tmp_path, fake_settings):
    audio_path = tmp_path / "demo.wav"
    audio_path.write_bytes(b"fake audio payload")

    fake_settings()
    service = TranscriptionService()

    collected: list[dict] = []
    result = service.transcribe(audio_path, token_callback=collected.append)

    assert "Transcripción simulada" in result["text"]
    assert result["segments"][0]["text"].startswith("Transcripción simulada")
    assert collected, "expected simulated tokens to be emitted"


def test_respects_settings_cache_and_token(fake_settings):
    settings = fake_settings(huggingface_token="hf_token", whisper_model_size="small", whisper_device="cuda")

    captured: dict[str, dict] = {}

    def factory(model_name: str, **kwargs):
        captured["model"] = model_name
        captured["kwargs"] = kwargs
        return DummyModel()

    service = TranscriptionService(model_factory=factory)

    service.transcribe(Path("demo.wav"))

    cache_dir = Path(settings.models_cache_dir)
    assert cache_dir.exists()
    assert captured["model"] == settings.whisper_model_size
    assert captured["kwargs"]["device"] == settings.whisper_device
    assert captured["kwargs"]["compute_type"] == settings.whisper_compute_type
    download_options = captured["kwargs"].get("download_options")
    assert download_options["cache_dir"] == str(cache_dir)
    assert download_options["token"] == settings.huggingface_token
