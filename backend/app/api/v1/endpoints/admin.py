import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path

from app.api.deps import get_admin_user
from app.db.session import get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.document import Document
from app.models.user import User
from app.models.voice_session import VoiceSession
from app.schemas.dashboard import DocumentOut
from app.schemas.chat import ConversationOut

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/documents", response_model=List[DocumentOut])
async def admin_list_docs(db: AsyncSession = Depends(get_db), admin: User = Depends(get_admin_user)):
    r = await db.execute(select(Document).order_by(Document.created_at.desc()).limit(500))
    return list(r.scalars().all())


@router.delete("/documents/{doc_id}")
async def admin_delete_doc(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    r = await db.execute(select(Document).where(Document.id == doc_id))
    doc = r.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Not found")
    Path(doc.storage_path).unlink(missing_ok=True)
    await db.delete(doc)
    await db.commit()
    return {"ok": True}


@router.get("/conversations", response_model=List[ConversationOut])
async def admin_list_conversations(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    r = await db.execute(select(Conversation).order_by(Conversation.updated_at.desc()).limit(min(limit, 500)))
    return list(r.scalars().all())


@router.delete("/conversations/{conversation_id}")
async def admin_delete_conversation(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    r = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = r.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=404, detail="Not found")
    await db.delete(conv)
    await db.commit()
    return {"ok": True}
