import logging
from typing import Optional

from app.services.intent_service import extract_search_query
from app.tools import search_tool, system_tool, time_tool
from app.tools.search_tool import SearchOutcome

logger = logging.getLogger(__name__)

STATUS_MESSAGES = {
    "time": "🕒 Checking time...",
    "search": "🔍 Searching web...",
    "system": "💻 Opening application...",
}


async def run_tool(intent: str, user_message: str) -> str:
    logger.info("Running tool: intent=%s", intent)
    if intent == "time":
        return time_tool.handle(user_message)
    if intent == "search":
        outcome = await run_search(user_message)
        if not outcome.ok:
            raise RuntimeError(outcome.error or "search failed")
        return outcome.formatted
    if intent == "system":
        return system_tool.open_app(user_message)
    raise ValueError(f"Unknown tool intent: {intent}")


async def run_search(user_message: str) -> SearchOutcome:
    query = extract_search_query(user_message)
    logger.info(
        "Search tool selected: raw_query=%r search_query=%r",
        user_message,
        query,
    )
    return await search_tool.search(query)


async def iter_search(user_message: str):
    query = extract_search_query(user_message)
    logger.info(
        "Search tool stream: raw_query=%r search_query=%r",
        user_message,
        query,
    )
    async for event in search_tool.iter_search(query):
        yield event


def status_message(intent: str) -> Optional[str]:
    return STATUS_MESSAGES.get(intent)
