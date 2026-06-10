import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.document import Document
from app.models.user import User
from app.schemas.dashboard import DocumentOut
from app.services.analytics_service import log_event
from app.services.rag_service import ingest_file

router = APIRouter(prefix="/documents", tags=["documents"])
logger = logging.getLogger(__name__)

ALLOWED_EXT = {"pdf", "txt", "md", "docx"}


def _safe_name(name: str) -> str:
    base = os.path.basename(name)
    return base.replace("..", "").replace("/", "").replace("\\", "")[:500]


@router.get("", response_model=list[DocumentOut])
async def list_docs(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    r = await db.execute(select(Document).where(Document.user_id == user.id).order_by(Document.created_at.desc()))
    return list(r.scalars().all())


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_doc(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    fname = _safe_name(file.filename or "upload")
    ext = fname.lower().rsplit(".", 1)[-1] if "." in fname else ""
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"Unsupported type. Allowed: {sorted(ALLOWED_EXT)}")

    data = await file.read()
    max_b = settings.max_upload_mb * 1024 * 1024
    if len(data) > max_b:
        raise HTTPException(status_code=413, detail="File too large")

    os.makedirs(settings.upload_dir, exist_ok=True)
    uid = str(uuid.uuid4())
    storage = str(Path(settings.upload_dir) / f"{user.id}_{uid}_{fname}")
    Path(storage).write_bytes(data)

    mime = file.content_type or "application/octet-stream"
    doc = Document(
        user_id=user.id,
        filename=fname,
        mime_type=mime,
        storage_path=storage,
        chunk_count=0,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    try:
        chunks = await ingest_file(user.id, storage, fname)
        doc.chunk_count = chunks
        await db.commit()
        await db.refresh(doc)
    except Exception as e:
        logger.exception(
            "ingest failed: doc_id=%s filename=%s error_type=%s error=%s",
            doc.id,
            fname,
            type(e).__name__,
            e,
        )
        await log_event(
            db,
            user_id=user.id,
            event_type="document_ingest_error",
            meta={
                "error": str(e),
                "error_type": type(e).__name__,
                "doc_id": str(doc.id),
            },
        )
        raise HTTPException(status_code=500, detail="Ingest failed; file stored but not indexed") from e

    await log_event(db, user_id=user.id, event_type="document_upload", meta={"doc_id": str(doc.id), "chunks": doc.chunk_count})
    return doc


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_doc(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    r = await db.execute(select(Document).where(Document.id == doc_id, Document.user_id == user.id))
    doc = r.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        Path(doc.storage_path).unlink(missing_ok=True)
    except Exception:
        pass
    await db.delete(doc)
    await db.commit()
