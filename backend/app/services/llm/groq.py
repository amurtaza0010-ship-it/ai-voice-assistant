import json
import logging
from typing import Dict

from app.core.config import Settings
from app.services.llm.base import ChatCompletionProvider

logger = logging.getLogger(__name__)


class GroqProvider(ChatCompletionProvider):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def name(self) -> str:
        return "groq"

    def api_key(self) -> str:
        return self._settings.groq_api_key

    def chat_url(self) -> str:
        return self._settings.groq_chat_url

    def headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._settings.groq_api_key}",
            "Content-Type": "application/json",
        }

    def primary_model(self) -> str:
        return self._settings.groq_model

    def fallback_model(self) -> str:
        return self._settings.groq_fallback_model

    def max_tokens(self) -> int:
        return self._settings.groq_max_tokens

    def format_error(self, status_code: int, body: str) -> str:
        try:
            data = json.loads(body)
            err = data.get("error", data)
            if isinstance(err, dict):
                message = (
                    err.get("message")
                    or err.get("detail")
                    or "Groq request failed"
                )
                if status_code == 401:
                    return (
                        "Groq rejected the API key (401). "
                        "Verify GROQ_API_KEY in backend/.env."
                    )
                if status_code == 429:
                    return "Groq rate limit exceeded (429). Retry shortly."
                return f"Groq error ({status_code}): {message}"
        except json.JSONDecodeError:
            pass
        snippet = body[:500].strip() or "(empty response body)"
        return f"Groq error ({status_code}): {snippet}"
