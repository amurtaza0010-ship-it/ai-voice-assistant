import logging
import re
from typing import Literal

logger = logging.getLogger(__name__)

IntentType = Literal["time", "search", "system", "close", "chat"]

_TIME_RE = re.compile(
    r"\b("
    r"time|date|clock|timezone|tareekh|din|"
    r"baj\s*rahe|kitne\s*baj|samay|waqt"
    r")\b",
    re.IGNORECASE,
)

_SEARCH_RE = re.compile(
    r"\b("
    r"search|latest|news|updates?|headlines|"
    r"web\s*search|google|duckduckgo|"
    r"kya\s+hai|what\s+is|who\s+is|"
    r"ai\s+news|technology\s+news|tech\s+news|"
    r"openai|langgraph"
    r")\b",
    re.IGNORECASE,
)

_DOCUMENT_QUERY_RE = re.compile(
    r"\b("
    r"my\s+document|uploaded\s+file|knowledge\s+base|"
    r"according\s+to\s+(the\s+)?(document|file|pdf)|"
    r"in\s+(the\s+)?(document|file|pdf)|"
    r"summarize\s+(my|the)\s+(document|file|upload)"
    r")\b",
    re.IGNORECASE,
)

_SYSTEM_RE = re.compile(
    r"\b("
    r"open|launch|start|kholo|khol\s*do|run"
    r")\b",
    re.IGNORECASE,
)

_CLOSE_RE = re.compile(
    r"\b("
    r"close|exit|quit|band\s*karo|band\s*kar|band\s*kado|"
    r"bند\s*کرو|shut|kill|terminate"
    r")\b",
    re.IGNORECASE,
)

_APP_RE = re.compile(
    r"\b("
    r"notepad|calculator|chrome|edge|vs\s*code|vscode|"
    r"file\s*explorer|explorer"
    r")\b",
    re.IGNORECASE,
)

_FILLER_WORDS_RE = re.compile(
    r"\b(batao|batado|please|tell\s+me|mujhe|bata|dikhao)\b",
    re.IGNORECASE,
)


def extract_search_query(text: str) -> str:
    cleaned = _FILLER_WORDS_RE.sub("", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ?.,!")
    return cleaned or text.strip()


def _is_search_query(text: str) -> bool:
    return bool(_SEARCH_RE.search(text))


def _is_document_query(text: str) -> bool:
    return bool(_DOCUMENT_QUERY_RE.search(text))


def detect_intent(text: str, *, has_rag_context: bool = False) -> IntentType:
    cleaned = (text or "").strip()
    if not cleaned:
        return "chat"

    # Close intent — check before system so "close calculator" doesn't match "open"
    if _CLOSE_RE.search(cleaned) and _APP_RE.search(cleaned):
        intent: IntentType = "close"
        logger.info(
            "Intent detected: intent=%s query=%r rag_context=%s reason=close_command",
            intent,
            cleaned,
            has_rag_context,
        )
        return intent

    if _SYSTEM_RE.search(cleaned) and _APP_RE.search(cleaned):
        intent = "system"
        logger.info(
            "Intent detected: intent=%s query=%r rag_context=%s reason=system_command",
            intent,
            cleaned,
            has_rag_context,
        )
        return intent

    if _TIME_RE.search(cleaned):
        intent = "time"
        logger.info(
            "Intent detected: intent=%s query=%r rag_context=%s reason=time_query",
            intent,
            cleaned,
            has_rag_context,
        )
        return intent

    if _is_search_query(cleaned):
        if _is_document_query(cleaned):
            intent = "chat"
            logger.info(
                "Intent detected: intent=%s query=%r rag_context=%s reason=document_query_overrides_search",
                intent,
                cleaned,
                has_rag_context,
            )
            return intent

        intent = "search"
        reason = "explicit_web_search"
        if has_rag_context:
            reason = "web_search_overrides_rag_context"
        logger.info(
            "Intent detected: intent=%s query=%r rag_context=%s reason=%s search_query=%r",
            intent,
            cleaned,
            has_rag_context,
            reason,
            extract_search_query(cleaned),
        )
        return intent

    intent = "chat"
    fallback_reason = "no_tool_pattern_matched"
    if has_rag_context:
        fallback_reason = "rag_chat"
    logger.info(
        "Intent detected: intent=%s query=%r rag_context=%s reason=%s",
        intent,
        cleaned,
        has_rag_context,
        fallback_reason,
    )
    return intent