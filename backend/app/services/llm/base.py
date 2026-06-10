from abc import ABC, abstractmethod
from typing import Dict, Optional


class ChatCompletionProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def api_key(self) -> str:
        ...

    @abstractmethod
    def chat_url(self) -> str:
        ...

    @abstractmethod
    def headers(self) -> Dict[str, str]:
        ...

    @abstractmethod
    def primary_model(self) -> str:
        ...

    @abstractmethod
    def fallback_model(self) -> str:
        ...

    @abstractmethod
    def max_tokens(self) -> int:
        ...

    def resolve_model(self, model: Optional[str]) -> str:
        return model or self.primary_model()

    @abstractmethod
    def format_error(self, status_code: int, body: str) -> str:
        ...

    def log_request(self, model: str, *, stream: bool = True, follow_up: bool = False) -> None:
        phase = "tool follow-up" if follow_up else "chat completion"
        import logging

        logging.getLogger(__name__).info(
            "%s request: provider=%s endpoint=%s model=%s max_tokens=%d stream=%s key_length=%d",
            phase,
            self.name,
            self.chat_url(),
            model,
            self.max_tokens(),
            stream,
            len(self.api_key()),
        )

    def log_startup_diagnostics(self) -> None:
        import logging

        key = self.api_key()
        logging.getLogger(__name__).info(
            "LLM provider: name=%s key_present=%s key_length=%d model=%s fallback_model=%s max_tokens=%d endpoint=%s",
            self.name,
            bool(key),
            len(key),
            self.primary_model(),
            self.fallback_model(),
            self.max_tokens(),
            self.chat_url(),
        )

    def should_retry_with_fallback(self, status_code: int, body: str) -> bool:
        if status_code in (404, 422):
            return True
        lowered = body.lower()
        return "model" in lowered and (
            "not found" in lowered
            or "does not exist" in lowered
            or "decommissioned" in lowered
        )
