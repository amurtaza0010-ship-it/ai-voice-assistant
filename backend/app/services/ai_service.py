import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from app.services.intent_service import detect_intent, extract_search_query
from app.services.llm import ChatCompletionProvider, get_chat_provider
from app.tools import tool_registry

logger = logging.getLogger(__name__)

ENGLISH_SYSTEM_INSTRUCTION = (
    "Always respond in English. "
    "Do not use Hindi, Urdu, or any other language unless the user explicitly requests it."
)

SEARCH_SUMMARY_INSTRUCTION = (
    "Answer using ONLY the provided web search results below. "
    "Summarize the findings clearly in English with source titles or URLs when helpful. "
    "Do NOT say you lack access to real-time information. "
    "Do NOT claim you cannot browse the web."
)

TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Return the current UTC time in ISO format.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Evaluate arithmetic expressions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                    }
                },
                "required": ["expression"],
            },
        },
    },
]


def _yield_status(intent: str) -> str:
    message = tool_registry.status_message(intent) or "Working..."
    return json.dumps({"type": "status", "data": message})


def _yield_token(text: str) -> str:
    return json.dumps({"type": "token", "data": text})


def _yield_done() -> str:
    return json.dumps(
        {
            "type": "done",
            "data": {"message_id": "assistant-final"},
        }
    )


def _tool_dispatch(
    name: str,
    arguments: str,
) -> str:
    from datetime import datetime, timezone

    try:
        args = json.loads(arguments) if arguments else {}
    except json.JSONDecodeError:
        return "Invalid JSON arguments."

    if name == "get_current_time":
        return datetime.now(timezone.utc).isoformat()

    if name == "calculator":
        from app.utils.safe_calc import safe_eval_expr

        expr = str(args.get("expression", "")).strip()

        try:
            return str(safe_eval_expr(expr))
        except Exception as e:
            return str(e)

    return f"Unknown tool: {name}"


def _chat_payload(
    provider: ChatCompletionProvider,
    *,
    model: str,
    messages: List[Dict[str, Any]],
    stream: bool = True,
    use_tools: bool = False,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "max_tokens": provider.max_tokens(),
    }
    if use_tools:
        payload["tools"] = TOOLS
        payload["tool_choice"] = "auto"
    return payload


async def _collect_tool_calls(
    resp: httpx.Response,
) -> tuple[Dict[int, Dict[str, Any]], List[str]]:
    tool_calls: Dict[int, Dict[str, Any]] = {}
    tokens: List[str] = []

    async for line in resp.aiter_lines():
        if not line or not line.startswith("data: "):
            continue

        data = line[6:]

        if data.strip() == "[DONE]":
            break

        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue

        choice = (chunk.get("choices") or [{}])[0]
        delta = choice.get("delta") or {}

        if delta.get("content"):
            tokens.append(
                json.dumps(
                    {
                        "type": "token",
                        "data": delta["content"],
                    }
                )
            )

        for tc in delta.get("tool_calls") or []:
            idx = int(tc.get("index", 0))
            entry = tool_calls.setdefault(
                idx,
                {
                    "id": "",
                    "name": "",
                    "arguments": "",
                },
            )

            if tc.get("id"):
                entry["id"] = tc["id"]

            fn = tc.get("function") or {}

            if fn.get("name"):
                entry["name"] += fn["name"]

            if fn.get("arguments"):
                entry["arguments"] += fn["arguments"]

    return tool_calls, tokens


async def _stream_provider_completion(
    client: httpx.AsyncClient,
    provider: ChatCompletionProvider,
    payload: Dict[str, Any],
    *,
    follow_up: bool = False,
) -> AsyncIterator[str]:
    model = str(payload.get("model", ""))
    provider.log_request(model, stream=True, follow_up=follow_up)

    async with client.stream(
        "POST",
        provider.chat_url(),
        headers=provider.headers(),
        json=payload,
    ) as resp:
        if resp.status_code >= 400:
            text = (await resp.aread()).decode(errors="ignore")
            error_message = provider.format_error(resp.status_code, text)
            logger.error(
                "%s failed: provider=%s status=%s model=%s endpoint=%s body=%s",
                "Tool follow-up" if follow_up else "Chat completion",
                provider.name,
                resp.status_code,
                model,
                provider.chat_url(),
                text[:2000],
            )
            yield json.dumps(
                {
                    "type": "error",
                    "data": error_message,
                }
            )
            return

        tool_calls, tokens = await _collect_tool_calls(resp)

        for token in tokens:
            yield token

        if tool_calls:
            assistant_tool_calls = []

            for _, tc in sorted(tool_calls.items()):
                assistant_tool_calls.append(
                    {
                        "id": tc.get("id") or "call",
                        "type": "function",
                        "function": {
                            "name": tc.get("name", ""),
                            "arguments": tc.get("arguments", ""),
                        },
                    }
                )

            tool_messages = []

            for tc in assistant_tool_calls:
                result = _tool_dispatch(
                    tc["function"]["name"],
                    tc["function"].get("arguments", ""),
                )
                tool_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    }
                )

            follow_messages = (
                list(payload["messages"])
                + [
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": assistant_tool_calls,
                    }
                ]
                + tool_messages
            )
            follow_payload = _chat_payload(
                provider,
                model=model,
                messages=follow_messages,
                stream=True,
                use_tools=False,
            )

            async for chunk in _stream_provider_completion(
                client,
                provider,
                follow_payload,
                follow_up=True,
            ):
                yield chunk
            return


async def stream_chat_completion(
    messages: List[Dict[str, str]],
    *,
    model: Optional[str] = None,
    extra_context: Optional[str] = None,
    use_tools: bool = True,
) -> AsyncIterator[str]:
    provider = get_chat_provider()

    if not provider.api_key():
        yield json.dumps(
            {
                "type": "error",
                "data": "GROQ_API_KEY missing",
            }
        )
        return

    user_text = ""
    for msg in reversed(messages):
        if msg.get("role") == "user" and (msg.get("content") or "").strip():
            user_text = str(msg["content"]).strip()
            break

    has_rag_context = bool(extra_context)
    intent = detect_intent(
        user_text,
        has_rag_context=has_rag_context,
    )

    logger.info(
        "Routing query: intent=%s tool=%s rag_context=%s query=%r",
        intent,
        intent if intent in ("time", "search", "system") else "groq_chat",
        has_rag_context,
        user_text,
    )

    if intent in ("time", "system"):
        yield _yield_status(intent)
        try:
            result = await tool_registry.run_tool(intent, user_text)
        except Exception as e:
            logger.exception("Tool execution failed: intent=%s", intent)
            yield json.dumps({"type": "error", "data": str(e)})
            return
        yield _yield_token(result)
        yield _yield_done()
        return

    search_context: Optional[str] = None
    if intent == "search":
        yield _yield_status(intent)
        search_query = extract_search_query(user_text)
        outcome = None
        async for event in tool_registry.iter_search(user_text):
            if event.get("type") == "status":
                yield json.dumps({"type": "status", "data": event["data"]})
            elif event.get("type") == "result":
                outcome = event["outcome"]
        if outcome is None:
            yield json.dumps({"type": "error", "data": "Search tool failed: no result"})
            return
        logger.info(
            "Search execution: selected_tool=search raw_query=%r search_query=%r "
            "result_count=%d ok=%s fallback_reason=%s",
            user_text,
            search_query,
            outcome.result_count,
            outcome.ok,
            None if outcome.ok else outcome.error,
        )
        if not outcome.ok:
            reason = outcome.error or "unknown error"
            logger.error(
                "Search tool failed; not falling back to generic chat: query=%r reason=%s",
                search_query,
                reason,
            )
            yield _yield_token(f"Search tool failed: {reason}")
            yield _yield_done()
            return
        search_context = outcome.formatted

    selected_model = provider.resolve_model(model)
    fallback_model = provider.fallback_model()

    sys_parts = [
        "You are VoiceAI, a concise helpful assistant.",
        ENGLISH_SYSTEM_INSTRUCTION,
    ]

    if extra_context:
        sys_parts.append(extra_context)

    if search_context:
        sys_parts.append(
            f"{SEARCH_SUMMARY_INSTRUCTION}\n\n{search_context}"
        )

    full_messages = [
        {
            "role": "system",
            "content": "\n\n".join(sys_parts),
        }
    ]
    full_messages.extend(messages)

    async with httpx.AsyncClient(timeout=120.0) as client:
        models_to_try = [selected_model]
        if fallback_model and fallback_model != selected_model:
            models_to_try.append(fallback_model)

        for attempt_index, attempt_model in enumerate(models_to_try):
            payload = _chat_payload(
                provider,
                model=attempt_model,
                messages=full_messages,
                stream=True,
                use_tools=use_tools,
            )

            provider.log_request(attempt_model, stream=True)

            async with client.stream(
                "POST",
                provider.chat_url(),
                headers=provider.headers(),
                json=payload,
            ) as resp:
                if resp.status_code >= 400:
                    text = (await resp.aread()).decode(errors="ignore")
                    can_retry = (
                        attempt_index == 0
                        and len(models_to_try) > 1
                        and provider.should_retry_with_fallback(
                            resp.status_code,
                            text,
                        )
                    )
                    if can_retry:
                        logger.warning(
                            "Primary model failed; retrying with fallback: primary=%s fallback=%s status=%s",
                            attempt_model,
                            fallback_model,
                            resp.status_code,
                        )
                        continue

                    error_message = provider.format_error(
                        resp.status_code,
                        text,
                    )
                    logger.error(
                        "Chat completion failed: provider=%s status=%s model=%s endpoint=%s body=%s",
                        provider.name,
                        resp.status_code,
                        attempt_model,
                        provider.chat_url(),
                        text[:2000],
                    )
                    yield json.dumps(
                        {
                            "type": "error",
                            "data": error_message,
                        }
                    )
                    return

                tool_calls, tokens = await _collect_tool_calls(resp)

                for token in tokens:
                    yield token

                if tool_calls:
                    assistant_tool_calls = []

                    for _, tc in sorted(tool_calls.items()):
                        assistant_tool_calls.append(
                            {
                                "id": tc.get("id") or "call",
                                "type": "function",
                                "function": {
                                    "name": tc.get("name", ""),
                                    "arguments": tc.get("arguments", ""),
                                },
                            }
                        )

                    tool_messages = []

                    for tc in assistant_tool_calls:
                        result = _tool_dispatch(
                            tc["function"]["name"],
                            tc["function"].get("arguments", ""),
                        )
                        tool_messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": result,
                            }
                        )

                    follow_messages = (
                        full_messages
                        + [
                            {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": assistant_tool_calls,
                            }
                        ]
                        + tool_messages
                    )
                    follow_payload = _chat_payload(
                        provider,
                        model=attempt_model,
                        messages=follow_messages,
                        stream=True,
                        use_tools=False,
                    )

                    async for chunk in _stream_provider_completion(
                        client,
                        provider,
                        follow_payload,
                        follow_up=True,
                    ):
                        yield chunk
                    return

                break

    yield _yield_done()


async def count_tokens_estimate(
    text: str,
) -> int:
    return max(1, len(text) // 4)
