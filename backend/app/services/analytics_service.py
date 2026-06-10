import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics_event import AnalyticsEvent
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.message import Message
from app.models.voice_session import VoiceSession

logger = logging.getLogger(__name__)


async def log_event(
    db: AsyncSession,
    *,
    user_id: Optional[uuid.UUID],
    event_type: str,
    meta: Optional[dict] = None,
    tokens_prompt: Optional[int] = None,
    tokens_completion: Optional[int] = None,
) -> None:
    row = AnalyticsEvent(
        user_id=user_id,
        event_type=event_type,
        meta_json=json.dumps(meta) if meta else None,
        tokens_prompt=tokens_prompt,
        tokens_completion=tokens_completion,
    )
    db.add(row)
    try:
        await db.commit()
    except Exception as e:
        logger.warning("analytics commit failed: %s", e)
        await db.rollback()


async def dashboard_stats(db: AsyncSession, user_id: uuid.UUID) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=30)

    async def count(model, *filters):
        q = select(func.count()).select_from(model)
        for f in filters:
            q = q.where(f)
        r = await db.execute(q)
        return int(r.scalar() or 0)

    total_conversations = await count(Conversation, Conversation.user_id == user_id)
    msg_q = select(func.count()).select_from(Message).join(Conversation).where(Conversation.user_id == user_id)
    total_messages = int((await db.execute(msg_q)).scalar() or 0)
    total_voice = await count(VoiceSession, VoiceSession.user_id == user_id)
    total_docs = await count(Document, Document.user_id == user_id)

    tok_q = select(
        func.coalesce(func.sum(AnalyticsEvent.tokens_prompt), 0),
        func.coalesce(func.sum(AnalyticsEvent.tokens_completion), 0),
    ).where(AnalyticsEvent.user_id == user_id, AnalyticsEvent.created_at >= since)
    tr = await db.execute(tok_q)
    pr, comp = tr.one()

    return {
        "total_conversations": total_conversations,
        "total_messages": total_messages,
        "total_voice_sessions": total_voice,
        "total_documents": total_docs,
        "tokens_prompt_30d": int(pr or 0),
        "tokens_completion_30d": int(comp or 0),
    }
