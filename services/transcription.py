import json
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
TokenCallback = Callable[[dict[str, Any]], None]


class TranscriptionService:
    """Service responsible for running faster-whisper inference."""

    def __init__(
        self,
        model_size: str = "medium",
        quantization: Quantization = "float16",
        device: str = "auto",
        model_factory: Optional[Callable[..., WhisperModel]] = None,
    ) -> None:
        self.model_size = model_size
        self.quantization = quantization
        self.device = device
        self._model_factory = model_factory
        self._model: Optional[WhisperModel] = None
        # validate quantization eagerly to fail-fast in misconfigured environments
        self._map_quantization(self.quantization)

    @property
    def model(self) -> WhisperModel:
        if self._model is None:
            compute_type = self._map_quantization(self.quantization)
            factory = self._model_factory
            if factory is None:
                if _WhisperModel is None:  # pragma: no cover - dependency not installed
                    raise RuntimeError("faster-whisper is not installed")
                factory = _WhisperModel
            logger.info(
                "Loading faster-whisper model",
                extra={"model": self.model_size, "compute_type": compute_type},
            )
            self._model = factory(self.model_size, device=self.device, compute_type=compute_type)
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
            start = float(getattr(segment, "start", 0.0) or 0.0)
            end = float(getattr(segment, "end", start) or start)
            for token in segment.tokens:
                text = getattr(token, "text", "") or ""
                if not text:
                    continue
                transcript_tokens.append(text)
                if token_callback:
                    payload = {"text": text, "t0": start, "t1": end}
                    try:
                        token_callback(payload)
                    except Exception:  # pragma: no cover - defensive logging
                        logger.exception("Token callback raised", extra={"payload": json.dumps(payload)})

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
                    "start": float(getattr(segment, "start", 0.0) or 0.0),
                    "end": float(getattr(segment, "end", 0.0) or 0.0),
                    "text": getattr(segment, "text", ""),
                }
                for segment in segments
            ],
            "language": info.language,
            "duration": getattr(info, "duration", None),
        }


__all__ = ["TranscriptionService", "Quantization"]
