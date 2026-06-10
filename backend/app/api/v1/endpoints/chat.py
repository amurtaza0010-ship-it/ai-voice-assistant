import json
import logging
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.schemas.chat import ConversationCreate, ConversationDetail, ConversationOut, ConversationRename, MessageCreate, MessageOut
from app.services.ai_service import stream_chat_completion
from app.services.analytics_service import log_event
from app.services.ai_service import count_tokens_estimate
from app.services.rag_service import retrieve_context

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


@router.get("/conversations", response_model=List[ConversationOut])
async def list_conversations(
    q: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[Conversation]:
    stmt = select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.updated_at.desc())
    if q:
        stmt = stmt.where(Conversation.title.ilike(f"%{q}%"))
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/conversations", response_model=ConversationOut)
async def create_conversation(
    payload: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Conversation:
    conv = Conversation(user_id=user.id, title=payload.title or "New chat")
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Conversation:
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conversation_id, Conversation.user_id == user.id)
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.patch("/conversations/{conversation_id}", response_model=ConversationOut)
async def rename_conversation(
    conversation_id: uuid.UUID,
    payload: ConversationRename,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Conversation:
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user.id)
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv.title = payload.title
    await db.commit()
    await db.refresh(conv)
    return conv


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user.id)
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await db.delete(conv)
    await db.commit()


@router.post("/conversations/{conversation_id}/messages/stream")
async def stream_message(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user.id)
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    user_msg = Message(conversation_id=conv.id, role="user", content=payload.content)
    db.add(user_msg)
    await db.commit()

    hist = await db.execute(
        select(Message).where(Message.conversation_id == conv.id).order_by(Message.created_at.asc())
    )
    messages = [{"role": m.role, "content": m.content} for m in hist.scalars().all()]

    rag_context = await retrieve_context(user.id, payload.content)

    assistant_text: list[str] = []

    async def gen():
        full = ""
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
            new_title = conv.title
            if (conv.title or "").strip() in ("", "New chat"):
                new_title = (payload.content[:60] + ("…" if len(payload.content) > 60 else "")).strip() or "New chat"
            from datetime import datetime, timezone

            await db.execute(
                update(Conversation)
                .where(Conversation.id == conv.id)
                .values(updated_at=datetime.now(timezone.utc), title=new_title)
            )
            await db.commit()
            await db.refresh(asst)
            pr = await count_tokens_estimate(payload.content + (rag_context or ""))
            comp = await count_tokens_estimate(full)
            await log_event(
                db,
                user_id=user.id,
                event_type="chat_completion",
                meta={"conversation_id": str(conv.id)},
                tokens_prompt=pr,
                tokens_completion=comp,
            )
            yield f"data: {json.dumps({'type':'done','data':{'message_id':str(asst.id)}})}\n\n"
        except Exception as e:
            logger.exception("stream error")
            yield f"data: {json.dumps({'type':'error','data':str(e)})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
