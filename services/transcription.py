"""Wrapper around faster-whisper with streaming token emission."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Optional, TYPE_CHECKING

try:  # pragma: no cover - optional dependency
    from faster_whisper import WhisperModel as _WhisperModel
except ImportError:  # pragma: no cover - optional dependency
    _WhisperModel = None  # type: ignore

if TYPE_CHECKING:  # pragma: no cover
    from faster_whisper import WhisperModel
else:
    WhisperModel = Any

logger = logging.getLogger(__name__)


Quantization = str
TokenCallback = Callable[[str], None]


class TranscriptionService:
    """Service responsible for running faster-whisper inference."""

    def __init__(
        self,
        model_size: str = "medium",
        quantization: Quantization = "float16",
        device: str = "auto",
    ) -> None:
        self.model_size = model_size
        self.quantization = quantization
        self.device = device
        self._model: Optional[WhisperModel] = None

    @property
    def model(self) -> WhisperModel:
        if self._model is None:
            compute_type = self._map_quantization(self.quantization)
            if _WhisperModel is None:  # pragma: no cover - dependency not installed
                raise RuntimeError("faster-whisper is not installed")
            logger.info("Loading faster-whisper model", extra={"model": self.model_size, "compute_type": compute_type})
            self._model = _WhisperModel(self.model_size, device=self.device, compute_type=compute_type)
        return self._model

    @staticmethod
    def _map_quantization(quantization: Quantization) -> str:
        mapping = {
            "float32": "float32",
            "float16": "float16",
            "int8": "int8_float16",
        }
        if quantization not in mapping:
            raise ValueError(f"Unsupported quantization: {quantization}")
        return mapping[quantization]

    def transcribe(
        self,
        audio_path: Path,
        token_callback: Optional[TokenCallback] = None,
        language: Optional[str] = None,
    ) -> dict:
        """Run inference and optionally stream delta tokens through ``token_callback``."""

        segments_iterable, info = self.model.transcribe(str(audio_path), language=language)
        segments = list(segments_iterable)

        transcript_tokens: list[str] = []
        for segment in segments:
            for token in segment.tokens:
                text = token.text or ""
                if text:
                    transcript_tokens.append(text)
                    if token_callback:
                        token_callback(text)

        transcript_text = "".join(transcript_tokens).strip()
        logger.info(
            "Transcription complete",
            extra={
                "duration": info.duration,
                "language": info.language,
                "transcript_length": len(transcript_text),
            },
        )

        return {
            "text": transcript_text,
            "segments": [
                {
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text,
                }
                for segment in segments
            ],
            "language": info.language,
            "duration": info.duration,
        }

        
