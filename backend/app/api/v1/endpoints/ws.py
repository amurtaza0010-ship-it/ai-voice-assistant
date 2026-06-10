import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError
from sqlalchemy import select

from app.core.security import decode_token
from app.db.session import AsyncSessionLocal
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.services.ai_service import stream_chat_completion
from app.services.rag_service import retrieve_context

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


async def _user_from_token(token: str) -> User | None:
    sub = decode_token(token)
    if not sub:
        return None
    try:
        uid = uuid.UUID(sub)
    except ValueError:
        return None
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(User).where(User.id == uid, User.is_active.is_(True)))
        return r.scalar_one_or_none()


@router.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    await websocket.accept()
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401)
        return
    user = await _user_from_token(token)
    if user is None:
        await websocket.close(code=4401)
        return

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "data": "Invalid JSON"})
                continue

            action = payload.get("action", "chat")
            if action == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            conversation_id = payload.get("conversation_id")
            content = (payload.get("content") or "").strip()
            if not content:
                await websocket.send_json({"type": "error", "data": "Empty content"})
                continue

            async with AsyncSessionLocal() as db:
                conv = None
                if conversation_id:
                    try:
                        cid = uuid.UUID(str(conversation_id))
                    except ValueError:
                        await websocket.send_json({"type": "error", "data": "Bad conversation_id"})
                        continue
                    r = await db.execute(
                        select(Conversation).where(Conversation.id == cid, Conversation.user_id == user.id)
                    )
                    conv = r.scalar_one_or_none()
                    if conv is None:
                        await websocket.send_json({"type": "error", "data": "Conversation not found"})
                        continue
                else:
                    conv = Conversation(user_id=user.id, title="WebSocket chat")
                    db.add(conv)
                    await db.commit()
                    await db.refresh(conv)
                    await websocket.send_json({"type": "conversation", "data": {"id": str(conv.id)}})

                db.add(Message(conversation_id=conv.id, role="user", content=content))
                await db.commit()

                r = await db.execute(
                    select(Message).where(Message.conversation_id == conv.id).order_by(Message.created_at.asc())
                )
                messages = [{"role": m.role, "content": m.content} for m in r.scalars().all()]
                rag_context = await retrieve_context(user.id, content)

            full = ""
            async for chunk_json in stream_chat_completion(messages, extra_context=rag_context):
                await websocket.send_text(chunk_json)
                try:
                    data = json.loads(chunk_json)
                    if data.get("type") == "token":
                        full += data.get("data") or ""
                except json.JSONDecodeError:
                    pass

            async with AsyncSessionLocal() as db:
                db.add(Message(conversation_id=conv.id, role="assistant", content=full))
                await db.commit()

            await websocket.send_json({"type": "done", "data": {"conversation_id": str(conv.id)}})

    except WebSocketDisconnect:
        logger.info("WS disconnect user=%s", user.id)
    except Exception as e:
        logger.exception("WS error")
        try:
            await websocket.send_json({"type": "error", "data": str(e)})
        except Exception:
            pass
