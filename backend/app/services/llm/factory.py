from functools import lru_cache

from app.core.config import settings
from app.services.llm.base import ChatCompletionProvider
from app.services.llm.groq import GroqProvider


@lru_cache
def get_chat_provider() -> ChatCompletionProvider:
    return GroqProvider(settings)
