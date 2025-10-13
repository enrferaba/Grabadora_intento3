from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

try:  # pragma: no cover - optional dependency
    from faster_whisper import WhisperModel as _WhisperModel
except ImportError:  # pragma: no cover - optional dependency
    _WhisperModel = None  # type: ignore

if TYPE_CHECKING:  # pragma: no cover
    from faster_whisper import WhisperModel
else:
    WhisperModel = Any

from app.config import get_settings

logger = logging.getLogger(__name__)


Quantization = str
TokenCallback = Callable[[dict[str, Any]], None]


class TranscriptionService:
    """Service responsible for running faster-whisper inference."""

    def __init__(
        self,
        model_size: str | None = None,
        quantization: Quantization | None = None,
        device: str | None = None,
        model_factory: Optional[Callable[..., WhisperModel]] = None,
        *,
        cache_dir: str | Path | None = None,
        download_options: Optional[Dict[str, Any]] = None,
    ) -> None:
        settings = get_settings()

        resolved_model_size = (model_size or settings.whisper_model_size or "medium").strip()
        if not resolved_model_size:
            resolved_model_size = "medium"

        resolved_device = (device or settings.whisper_device or "auto").strip().lower() or "auto"

        resolved_quantization = quantization or settings.transcription_quantization or "float16"

        compute_type_override = (settings.whisper_compute_type or "").strip() or None

        cache_root = cache_dir or settings.models_cache_dir or "models"
        cache_path = Path(cache_root).expanduser()
        try:
            cache_path.mkdir(parents=True, exist_ok=True)
        except OSError:  # pragma: no cover - filesystem permission edge case
            logger.exception("Unable to create model cache directory", extra={"path": str(cache_path)})
        else:
            os.environ.setdefault("CTranslate2_CACHE_DIR", str(cache_path))

        dl_options: Dict[str, Any] = {}
        if download_options:
            dl_options.update(download_options)
        dl_options.setdefault("cache_dir", str(cache_path))
        hf_token = getattr(settings, "huggingface_token", None)
        if hf_token and not dl_options.get("token"):
            dl_options["token"] = hf_token

        self.model_size = resolved_model_size
        self.quantization = resolved_quantization
        self.device = resolved_device
        self._model_factory = model_factory
        self._model: Optional[WhisperModel] = None
        self._compute_type_override = compute_type_override
        self._download_options = dl_options
        self._simulate = _WhisperModel is None and model_factory is None
        # validate quantization eagerly to fail-fast in misconfigured environments
        if self._compute_type_override is None:
            self._map_quantization(self.quantization)

    @property
    def model(self) -> WhisperModel:
        if self._model is None:
            compute_type = self._compute_type_override or self._map_quantization(self.quantization)
            factory = self._model_factory
            if factory is None:
                if _WhisperModel is None:  # pragma: no cover - dependency not installed
                    raise RuntimeError("faster-whisper is not installed")
                factory = _WhisperModel
            factory_kwargs: Dict[str, Any] = {
                "device": self.device,
                "compute_type": compute_type,
            }
            if self._download_options:
                factory_kwargs["download_options"] = dict(self._download_options)
            logger.info(
                "Loading faster-whisper model",
                extra={
                    "model": self.model_size,
                    "compute_type": compute_type,
                    "device": self.device,
                    "cache_dir": self._download_options.get("cache_dir"),
                },
            )
            self._model = factory(self.model_size, **factory_kwargs)
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

        if self._simulate:
            return self._simulate_transcription(audio_path, token_callback, language)

        try:
            segments_iterable, info = self.model.transcribe(str(audio_path), language=language)
        except RuntimeError:
            # ``model`` property raises ``RuntimeError`` when faster-whisper is missing. In that
            # scenario we provide a deterministic simulated transcript so the rest of the app can
            # still be exercised locally.
            logger.warning("faster-whisper unavailable, returning simulated transcript")
            return self._simulate_transcription(audio_path, token_callback, language)
        except Exception:  # pragma: no cover - defensive fallback
            logger.exception("Unable to run faster-whisper; returning simulated transcript")
            return self._simulate_transcription(audio_path, token_callback, language)

        segments = list(segments_iterable)

        transcript_tokens: list[str] = []
        for segment_index, segment in enumerate(segments):
            start = float(getattr(segment, "start", 0.0) or 0.0)
            end = float(getattr(segment, "end", start) or start)
            for token in getattr(segment, "tokens", []) or []:
                text = getattr(token, "text", "") or ""
                if not text:
                    continue
                transcript_tokens.append(text)
                if token_callback:
                    payload = {"text": text, "t0": start, "t1": end, "segment": segment_index}
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

    def _simulate_transcription(
        self,
        audio_path: Path,
        token_callback: Optional[TokenCallback],
        language: Optional[str],
    ) -> dict:
        file_name = audio_path.name or "audio"
        simulated_language = language or "es"
        message = (
            f"Transcripción simulada para {file_name}. Instala faster-whisper para obtener resultados reales."
        )
        words = message.split(" ")
        pieces: list[str] = []
        for index, word in enumerate(words):
            suffix = " " if index < len(words) - 1 else ""
            token_text = f"{word}{suffix}"
            pieces.append(token_text)
            if token_callback:
                payload = {"text": token_text, "t0": index * 0.6, "t1": (index + 1) * 0.6, "segment": index}
                try:
                    token_callback(payload)
                except Exception:  # pragma: no cover - defensive
                    logger.exception("Token callback raised during simulation", extra={"payload": json.dumps(payload)})

        transcript_text = "".join(pieces).strip()
        duration = round(len(words) * 0.6, 2)
        logger.info(
            "Generated simulated transcript",
            extra={"file": file_name, "language": simulated_language, "duration": duration},
        )
        return {
            "text": transcript_text,
            "segments": [
                {
                    "start": 0.0,
                    "end": duration,
                    "text": transcript_text,
                }
            ],
            "language": simulated_language,
            "duration": duration,
        }


__all__ = ["TranscriptionService", "Quantization"]
