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

        resolved_device = (device or settings.whisper_device or "cuda").strip().lower() or "cuda"


        resolved_quantization = quantization or settings.transcription_quantization or "float16"
        compute_type_override = (settings.whisper_compute_type or "").strip() or None

        logger.info(f"Using device: {resolved_device}, quantization: {resolved_quantization}")

        cache_root = cache_dir or settings.models_cache_dir or "models"
        cache_path = Path(cache_root).expanduser()
        try:
            cache_path.mkdir(parents=True, exist_ok=True)
        except OSError:
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

        # Ajuste automático de modelo si ejecuta en CPU
        if resolved_device in ("cpu", "auto"):
            if resolved_model_size not in ("tiny", "base", "small"):
                logger.warning("Reduciendo modelo a 'small' en CPU para evitar falta de memoria")
                resolved_model_size = "small"

        os.environ.setdefault("OMP_NUM_THREADS", "1")
        os.environ.setdefault("CT2_FORCE_CPU_ISA", "AVX2")

        self.model_size = resolved_model_size
        self.quantization = resolved_quantization
        self.device = resolved_device
        self._model_factory = model_factory
        self._model: Optional[WhisperModel] = None
        self._compute_type_override = compute_type_override
        self._download_options = dl_options
        self._simulate = False

        if _WhisperModel is None:
            logger.warning("faster-whisper no disponible; usando modo simulado")
            self._simulate = True

        if self._compute_type_override is None:
            self._map_quantization(self.quantization)

    @property
    def model(self) -> WhisperModel:
        if self._model is None:
            compute_type = self._compute_type_override or self._map_quantization(self.quantization)
            factory = self._model_factory or _WhisperModel
            if factory is None:
                raise RuntimeError("faster-whisper is not installed")

            logger.info(
                "Loading faster-whisper model",
                extra={
                    "model": self.model_size,
                    "compute_type": compute_type,
                    "device": self.device,
                },
            )

            self._model = factory(
                self.model_size,
                device=self.device,
                compute_type=compute_type,
            )

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
        """Run inference and stream partial tokens progressively."""

        if self._simulate:
            return self._simulate_transcription(audio_path, token_callback, language)

        # Mapeo de nombres comunes a códigos ISO
        lang_map = {
            "español": "es",
            "spanish": "es",
            "castellano": "es",
            "english": "en",
            "inglés": "en",
            "francés": "fr",
            "french": "fr",
            "alemán": "de",
            "german": "de",
            "italiano": "it",
            "italian": "it",
            "portugués": "pt",
            "portuguese": "pt",
        }
        if language:
            language = language.strip().lower()
            language = lang_map.get(language, language)

        try:
            segments_iterable, info = self.model.transcribe(
                str(audio_path),
                language=language,
                vad_filter=True,
                word_timestamps=True,
                beam_size=1,
            )
        except RuntimeError:
            logger.warning("faster-whisper unavailable, returning simulated transcript")
            return self._simulate_transcription(audio_path, token_callback, language)
        except Exception as e:
            logger.exception(f"Unable to run faster-whisper; returning simulated transcript: {e}")
            return self._simulate_transcription(audio_path, token_callback, language)

        transcript_tokens: list[str] = []
        segments: list[dict[str, Any]] = []

        # Recorremos directamente el generador en tiempo real
        for segment_index, segment in enumerate(segments_iterable):
            start = float(getattr(segment, "start", 0.0) or 0.0)
            end = float(getattr(segment, "end", start) or start)
            segment_text = getattr(segment, "text", "")
            segments.append(
                {"start": start, "end": end, "text": segment_text}
            )

            # Emitir cada token progresivamente
            for token in getattr(segment, "tokens", []) or []:
                text = getattr(token, "text", "") or ""
                if not text:
                    continue
                transcript_tokens.append(text)
                if token_callback:
                    payload = {"text": text, "t0": start, "t1": end, "segment": segment_index}
                    try:
                        token_callback(payload)
                    except Exception:
                        logger.exception("Token callback raised", extra={"payload": json.dumps(payload)})

            # Emitir snapshot por segmento (mejora visual)
            if token_callback and segment_text:
                try:
                    token_callback({"text": segment_text + " ", "t0": start, "t1": end, "segment": segment_index})
                except Exception:
                    logger.exception("Segment snapshot callback raised", extra={"segment": segment_index})

        transcript_text = "".join(transcript_tokens).strip()

        logger.info(
            "Transcription complete",
            extra={
                "duration": getattr(info, "duration", None),
                "language": getattr(info, "language", None),
                "transcript_length": len(transcript_text),
            },
        )

        return {
            "text": transcript_text,
            "segments": segments,
            "language": getattr(info, "language", None),
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
        message = f"Transcripción simulada para {file_name}. Instala faster-whisper para obtener resultados reales."
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
                except Exception:
                    logger.exception(
                        "Token callback raised during simulation",
                        extra={"payload": json.dumps(payload)},
                    )

        transcript_text = "".join(pieces).strip()
        duration = round(len(words) * 0.6, 2)
        logger.info(
            "Generated simulated transcript",
            extra={"file": file_name, "language": simulated_language, "duration": duration},
        )
        return {
            "text": transcript_text,
            "segments": [{"start": 0.0, "end": duration, "text": transcript_text}],
            "language": simulated_language,
            "duration": duration,
        }


__all__ = ["TranscriptionService", "Quantization"]
