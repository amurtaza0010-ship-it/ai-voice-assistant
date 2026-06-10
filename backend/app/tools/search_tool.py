import asyncio
import html
import logging
import random
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, List, Optional
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 600
_MAX_RETRIES = 1
_RATE_LIMIT_NOTICE = (
    "Search provider temporarily rate limited. Trying alternate source..."
)

_cache: dict[str, tuple[float, "SearchOutcome"]] = {}

USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) "
        "Gecko/20100101 Firefox/122.0"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Edge/122.0.0.0 Safari/537.36"
    ),
]

_HTML_TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class SearchOutcome:
    ok: bool
    query: str
    result_count: int
    formatted: str
    error: Optional[str] = None
    provider: Optional[str] = None
    retry_count: int = 0
    latency_ms: float = 0.0
    notices: List[str] = field(default_factory=list)


def _cache_key(query: str) -> str:
    return query.strip().lower()


def _get_cached(query: str) -> Optional[SearchOutcome]:
    key = _cache_key(query)
    entry = _cache.get(key)
    if not entry:
        return None
    cached_at, outcome = entry
    if time.time() - cached_at > CACHE_TTL_SECONDS:
        _cache.pop(key, None)
        return None
    logger.info(
        "Search cache hit: query=%r age_s=%.1f provider=%s",
        query,
        time.time() - cached_at,
        outcome.provider,
    )
    return outcome


def _set_cache(query: str, outcome: SearchOutcome) -> None:
    if outcome.ok:
        _cache[_cache_key(query)] = (time.time(), outcome)


def _ua_for_attempt(attempt: int) -> str:
    return USER_AGENTS[attempt % len(USER_AGENTS)]


def _is_rate_limit_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return (
        "ratelimit" in msg
        or "rate limit" in msg
        or " 202 " in msg
        or "too many requests" in msg
    )


def _sanitize_error(exc: BaseException | str) -> str:
    msg = str(exc).strip()
    lower = msg.lower()
    if _is_rate_limit_error(exc):
        return "all search providers are temporarily rate limited"
    if not msg or "traceback" in lower or "exception" in lower:
        return "search providers could not return results at this time"
    if len(msg) > 180:
        return msg[:180] + "..."
    return msg


def _clean_snippet(text: str) -> str:
    plain = _HTML_TAG_RE.sub("", text or "")
    return html.unescape(plain).strip()


def _normalize_item(title: str, url: str, snippet: str) -> dict:
    return {
        "title": (title or "").strip(),
        "url": (url or "").strip(),
        "snippet": _clean_snippet(snippet),
    }


def _dedupe_results(results: List[dict]) -> List[dict]:
    seen: set[str] = set()
    unique: List[dict] = []
    for item in results:
        url = item.get("url", "")
        key = url or item.get("title", "")
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _ddg_text_search(
    query: str,
    *,
    backend: str,
    max_results: int,
    user_agent: str,
) -> List[dict]:
    from duckduckgo_search import DDGS

    results: List[dict] = []
    headers = {"User-Agent": user_agent}
    with DDGS(headers=headers, timeout=20) as ddgs:
        for item in ddgs.text(
            query,
            max_results=max_results,
            backend=backend,
        ):
            results.append(
                _normalize_item(
                    item.get("title") or "",
                    item.get("href") or "",
                    item.get("body") or "",
                )
            )
    return results


def _rss_news_search(query: str, user_agent: str) -> List[dict]:
    url = (
        "https://news.google.com/rss/search?"
        f"q={quote(query)}&hl=en-US&gl=US&ceid=US:en"
    )
    response = httpx.get(
        url,
        headers={"User-Agent": user_agent},
        timeout=20.0,
        follow_redirects=True,
    )
    response.raise_for_status()

    results: List[dict] = []
    root = ET.fromstring(response.text)
    for item in root.findall(".//item"):
        results.append(
            _normalize_item(
                item.findtext("title") or "",
                item.findtext("link") or "",
                item.findtext("description") or "",
            )
        )
    return results


def _generic_web_fallback(query: str, user_agent: str) -> List[dict]:
    results: List[dict] = []

    response = httpx.get(
        "https://api.duckduckgo.com/",
        params={
            "q": query,
            "format": "json",
            "no_redirect": 1,
            "no_html": 1,
        },
        headers={"User-Agent": user_agent},
        timeout=15.0,
    )
    response.raise_for_status()
    data = response.json()

    if data.get("AbstractText"):
        results.append(
            _normalize_item(
                data.get("Heading") or query,
                data.get("AbstractURL") or "",
                data.get("AbstractText") or "",
            )
        )

    for topic in data.get("RelatedTopics") or []:
        if isinstance(topic, dict) and topic.get("Text"):
            results.append(
                _normalize_item(
                    topic.get("Text") or "",
                    topic.get("FirstURL") or "",
                    topic.get("Text") or "",
                )
            )

    try:
        from duckduckgo_search import DDGS

        with DDGS(headers={"User-Agent": user_agent}, timeout=15) as ddgs:
            for item in ddgs.news(query, max_results=5):
                results.append(
                    _normalize_item(
                        item.get("title") or "",
                        item.get("url") or "",
                        item.get("body") or "",
                    )
                )
    except Exception as exc:
        logger.warning("DuckDuckGo news sub-fallback failed: %s", exc)

    return results


async def _run_provider_with_retries(
    provider_name: str,
    fn: Callable[[str, str], List[dict]],
    query: str,
    notices: List[str],
    *,
    ua_offset: int = 0,
    on_status: Optional[Callable[[str], Any]] = None,
) -> tuple[List[dict], int]:
    last_error: Optional[Exception] = None
    retries_used = 0

    for attempt in range(_MAX_RETRIES):
        if attempt > 0:
            backoff = (2 ** (attempt - 1)) + random.uniform(0.1, 0.6)
            retries_used += 1
            await asyncio.sleep(backoff)

        user_agent = _ua_for_attempt(ua_offset + attempt)
        try:
            results = await asyncio.to_thread(fn, query, user_agent)
            if results:
                return results, retries_used
        except Exception as exc:
            last_error = exc
            if _is_rate_limit_error(exc):
                if _RATE_LIMIT_NOTICE not in notices:
                    notices.append(_RATE_LIMIT_NOTICE)
                if on_status:
                    on_status(_RATE_LIMIT_NOTICE)
                logger.warning(
                    "Search provider rate limited: provider=%s retry_count=%d query=%r",
                    provider_name,
                    attempt + 1,
                    query,
                )
            else:
                logger.warning(
                    "Search provider failed: provider=%s retry_count=%d query=%r error=%s",
                    provider_name,
                    attempt + 1,
                    query,
                    _sanitize_error(exc),
                )

    if last_error:
        logger.warning(
            "Search provider exhausted retries: provider=%s retry_count=%d query=%r",
            provider_name,
            _MAX_RETRIES,
            query,
        )
    return [], retries_used


def _format_results(query: str, results: List[dict], provider: str) -> str:
    lines = [f"Web search results for: {query}", f"Source: {provider}", ""]
    for idx, item in enumerate(results, start=1):
        lines.append(f"{idx}. {item['title']}")
        lines.append(f"   URL: {item['url']}")
        lines.append(f"   Snippet: {item['snippet']}")
        lines.append("")
    return "\n".join(lines).strip()


async def iter_search(
    query: str,
    max_results: int = 5,
) -> AsyncIterator[dict]:
    clean = (query or "").strip()
    notices: List[str] = []
    started = time.perf_counter()
    total_retries = 0
    status_events: List[str] = []

    def emit_status(message: str) -> None:
        if message not in status_events:
            status_events.append(message)

    if not clean:
        yield {
            "type": "result",
            "outcome": SearchOutcome(
                ok=False,
                query=clean,
                result_count=0,
                formatted="",
                error="empty search query",
                notices=notices,
            ),
        }
        return

    cached = _get_cached(clean)
    if cached:
        cached.notices = list(cached.notices)
        yield {"type": "result", "outcome": cached}
        return

    # RSS first — fast and reliable, DDG as fallback
    providers: list[tuple[str, Callable[[str, str], List[dict]], int]] = [
        (
            "rss-news",
            lambda q, ua: _rss_news_search(q, ua)[:max_results],
            0,
        ),
        (
            "duckduckgo-auto",
            lambda q, ua: _ddg_text_search(
                q, backend="auto", max_results=max_results, user_agent=ua
            ),
            4,
        ),
        (
            "duckduckgo-html",
            lambda q, ua: _ddg_text_search(
                q, backend="html", max_results=max_results, user_agent=ua
            ),
            8,
        ),
        (
            "generic-web",
            lambda q, ua: _generic_web_fallback(q, ua)[:max_results],
            12,
        ),
    ]

    accumulated: List[dict] = []

    for provider_name, provider_fn, ua_offset in providers:
        for prior in status_events:
            yield {"type": "status", "data": prior}

        results, retries_used = await _run_provider_with_retries(
            provider_name,
            provider_fn,
            clean,
            notices,
            ua_offset=ua_offset,
            on_status=emit_status,
        )
        total_retries += retries_used

        for msg in status_events:
            if msg not in notices:
                notices.append(msg)
            yield {"type": "status", "data": msg}

        if results:
            accumulated = _dedupe_results(accumulated + results)[:max_results]
            latency_ms = (time.perf_counter() - started) * 1000
            formatted = _format_results(clean, accumulated, provider_name)
            outcome = SearchOutcome(
                ok=True,
                query=clean,
                result_count=len(accumulated),
                formatted=formatted,
                provider=provider_name,
                retry_count=total_retries,
                latency_ms=latency_ms,
                notices=notices,
            )
            logger.info(
                "Search succeeded: provider=%s retry_count=%d result_count=%d "
                "latency_ms=%.1f query=%r",
                provider_name,
                total_retries,
                len(accumulated),
                latency_ms,
                clean,
            )
            _set_cache(clean, outcome)
            yield {"type": "result", "outcome": outcome}
            return

    latency_ms = (time.perf_counter() - started) * 1000
    error = _sanitize_error("all search providers are temporarily rate limited")
    logger.error(
        "Search failed across providers: retry_count=%d result_count=0 "
        "latency_ms=%.1f query=%r",
        total_retries,
        latency_ms,
        clean,
    )
    yield {
        "type": "result",
        "outcome": SearchOutcome(
            ok=False,
            query=clean,
            result_count=0,
            formatted="",
            error=error,
            provider=None,
            retry_count=total_retries,
            latency_ms=latency_ms,
            notices=notices,
        ),
    }


async def search(query: str, max_results: int = 5) -> SearchOutcome:
    outcome: Optional[SearchOutcome] = None
    async for event in iter_search(query, max_results=max_results):
        if event["type"] == "result":
            outcome = event["outcome"]
    assert outcome is not None
    return outcome