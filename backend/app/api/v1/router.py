from fastapi import APIRouter

from app.api.v1.endpoints import auth, chat, documents, analytics, admin, voice, ws

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(chat.router)
api_router.include_router(documents.router)
api_router.include_router(analytics.router)
api_router.include_router(admin.router)
api_router.include_router(voice.router)
api_router.include_router(ws.router)
