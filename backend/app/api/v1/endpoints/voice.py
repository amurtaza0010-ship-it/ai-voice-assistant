import json
import logging
import tempfile
from pathlib import Path
from typing import Optional
import uuid

from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.models.voice_session import VoiceSession
from app.services.ai_service import count_tokens_estimate, stream_chat_completion
from app.services.analytics_service import log_event
from app.services.rag_service import retrieve_context
from app.services.voice_service import synthesize_speech, transcribe_audio_file

router = APIRouter(prefix="/voice", tags=["voice"])
logger = logging.getLogger(__name__)


class VoiceReplyBody(BaseModel):
    conversation_id: Optional[uuid.UUID] = None
    transcript: str = Field(min_length=1, max_length=32000)


@router.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    suffix = Path(file.filename or "audio.webm").suffix or ".webm"
    data = await file.read()
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Too large")
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(data)
        path = Path(tmp.name)
    try:
        text = await transcribe_audio_file(path)
    finally:
        path.unlink(missing_ok=True)
    if not text:
        raise HTTPException(
            status_code=503,
            detail="Transcription unavailable. Set OPENAI_API_KEY for Whisper or use browser speech recognition.",
        )
    return {"text": text}


@router.post("/reply-stream")
async def voice_reply_stream(
    body: VoiceReplyBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    transcript = body.transcript.strip()
    if not transcript:
        raise HTTPException(status_code=400, detail="transcript required")

    conv = None
    if body.conversation_id:
        r = await db.execute(
            select(Conversation).where(Conversation.id == body.conversation_id, Conversation.user_id == user.id)
        )
        conv = r.scalar_one_or_none()
        if conv is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conv = Conversation(user_id=user.id, title="Voice session")
        db.add(conv)
        await db.commit()
        await db.refresh(conv)

    user_msg = Message(conversation_id=conv.id, role="user", content=f"[voice] {transcript}")
    db.add(user_msg)
    await db.commit()

    r = await db.execute(select(Message).where(Message.conversation_id == conv.id).order_by(Message.created_at.asc()))
    messages = [{"role": m.role, "content": m.content} for m in r.scalars().all()]
    rag_context = await retrieve_context(user.id, transcript)

    full = ""

    async def gen():
        nonlocal full
        stream_error = False
        try:
            async for chunk_json in stream_chat_completion(messages, extra_context=rag_context):
                data = json.loads(chunk_json)
                if data.get("type") == "token":
                    full += data.get("data") or ""
                if data.get("type") == "error":
                    stream_error = True
                yield f"data: {chunk_json}\n\n"
                if stream_error:
                    return
            asst = Message(conversation_id=conv.id, role="assistant", content=full)
            db.add(asst)
            sess = VoiceSession(
                user_id=user.id,
                transcript=transcript,
                assistant_reply=full,
                duration_ms=None,
            )
            db.add(sess)
            await db.commit()
            pr = await count_tokens_estimate(transcript + (rag_context or ""))
            comp = await count_tokens_estimate(full)
            await log_event(
                db,
                user_id=user.id,
                event_type="voice_completion",
                meta={"conversation_id": str(conv.id)},
                tokens_prompt=pr,
                tokens_completion=comp,
            )
            audio = await synthesize_speech(full)
            payload = {"type": "done", "data": {"conversation_id": str(conv.id), "has_tts": bool(audio)}}
            yield f"data: {json.dumps(payload)}\n\n"
        except Exception as e:
            logger.exception("voice stream")
            yield f"data: {json.dumps({'type':'error','data':str(e)})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/tts")
async def tts_endpoint(text: str = Body(..., min_length=1, max_length=4096), user: User = Depends(get_current_user)):
    audio = await synthesize_speech(text)
    if not audio:
        raise HTTPException(status_code=503, detail="TTS unavailable (set OPENAI_API_KEY)")
    return Response(content=audio, media_type="audio/mpeg")
