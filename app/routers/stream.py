from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import asyncio
import json
import logging
from pathlib import Path
from app.whisper_service import TranscriptionService

router = APIRouter(prefix="/transcribe", tags=["stream"])
logger = logging.getLogger(__name__)

@router.get("/{job_id}")
async def stream_transcription(job_id: str, request: Request):
    """Transcripción en tiempo real usando SSE."""
    service = TranscriptionService()
    audio_path = Path(f"storage/{job_id}.wav")

    if not audio_path.exists():
        return StreamingResponse(
            (f"event: error\ndata: {json.dumps({'detail': f'No se encontró el audio {job_id}'})}\n\n" for _ in range(1)),
            media_type="text/event-stream",
        )

    async def event_generator():
        buffer = []

        def on_token(token):
            text = token.get("text", "")
            if text.strip():
                buffer.append(token)

        # Lanza la transcripción en un hilo para no bloquear el async loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: service.transcribe(audio_path=audio_path, token_callback=on_token))

        # Envía tokens progresivamente
        for token in buffer:
            payload = json.dumps(token, ensure_ascii=False)
            yield f"event: delta\ndata: {payload}\n\n"
            await asyncio.sleep(0.02)

        # Envía evento final con el texto completo
        if result.get("text"):
            payload = json.dumps({"text": result["text"]}, ensure_ascii=False)
            yield f"event: completed\ndata: {payload}\n\n"
        else:
            yield "event: completed\ndata: {\"status\": \"done\"}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
