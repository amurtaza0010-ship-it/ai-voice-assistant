import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.voice_session import VoiceSession
from app.models.user import User
from app.schemas.dashboard import DashboardStats, VoiceSessionOut
from app.services.analytics_service import dashboard_stats

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard", response_model=DashboardStats)
async def stats(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)) -> DashboardStats:
    data = await dashboard_stats(db, user.id)
    return DashboardStats(**data)


@router.get("/voice-history", response_model=List[VoiceSessionOut])
async def voice_history(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    r = await db.execute(
        select(VoiceSession)
        .where(VoiceSession.user_id == user.id)
        .order_by(VoiceSession.created_at.desc())
        .limit(min(limit, 200))
    )
    return list(r.scalars().all())


@router.delete("/voice-history/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_voice_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    r = await db.execute(
        select(VoiceSession).where(
            VoiceSession.id == session_id,
            VoiceSession.user_id == user.id,
        )
    )
    session = r.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Voice session not found")
    await db.delete(session)
    await db.commit()
