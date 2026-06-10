import logging
from pathlib import Path
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


async def transcribe_audio_file(path: Path) -> Optional[str]:
    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY not set; cannot transcribe server-side.")
        return None
    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    async with httpx.AsyncClient(timeout=120.0) as client:
        with path.open("rb") as f:
            files = {"file": (path.name, f, "application/octet-stream")}
            data = {"model": settings.whisper_model}
            resp = await client.post(url, headers=headers, data=data, files=files)
    if resp.status_code >= 400:
        logger.error("Whisper error: %s", resp.text[:500])
        return None
    try:
        return resp.json().get("text")
    except Exception:
        return None


async def synthesize_speech(text: str) -> Optional[bytes]:
    if not settings.openai_api_key:
        return None
    url = "https://api.openai.com/v1/audio/speech"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.tts_model,
        "voice": settings.tts_voice,
        "input": text[:4096],
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
    if resp.status_code >= 400:
        logger.error("TTS error: %s", resp.text[:500])
        return None
    return resp.content
