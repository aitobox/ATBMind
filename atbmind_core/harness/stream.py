"""
ATBMind Pi-Style Stream Client
Lightweight, native SSE streaming client with incremental tool call argument assembly.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from atbmind_core.harness.types import (
    AgentEvent,
    AgentEventType,
    AgentMessage,
    Role,
    ToolCall,
    Usage,
)

logger = logging.getLogger("atbmind.harness.stream")

class StreamClientError(Exception):
    """Base exception for streaming operations."""
    pass

class StreamClient:
    """
    OpenAI-compatible SSE streaming client.
    Handles chunk-by-chunk event dispatching and tool call argument fragment stitching.
    """

    def __init__(
        self,
        base_url: str = "https://api.openai.com/v1",
        api_key: str = "",
        model: str = "gpt-4o",
        timeout: float = 60.0,
        max_retries: int = 3,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.transport = transport

        if self.base_url.endswith("/chat/completions"):
            self.endpoint = self.base_url
        else:
            self.endpoint = f"{self.base_url}/chat/completions"

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _should_retry(self, status_code: Optional[int], exc: Optional[Exception]) -> bool:
        if isinstance(exc, (httpx.NetworkError, httpx.TimeoutException)):
            return True
        if status_code in (429, 500, 502, 503, 504):
            return True
        return False

    async def stream_chat(
        self,
        messages: List[AgentMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        cancellation_token: Optional[asyncio.Event] = None,
    ) -> AsyncIterator[AgentEvent]:
        """
        Initiates a streaming chat completion and yields AgentEvents in real-time.
        """
        payload_messages: List[Dict[str, Any]] = []
        if system_prompt:
            # Check if messages already have leading system prompt
            if not (messages and messages[0].role == Role.SYSTEM):
                payload_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            payload_messages.append(msg.to_llm_dict())

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": payload_messages,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
        if temperature is not None:
            payload["temperature"] = temperature

        headers = self._get_headers()
        attempt = 0

        while attempt <= self.max_retries:
            attempt += 1
            try:
                async with httpx.AsyncClient(
                    transport=self.transport, timeout=self.timeout
                ) as client:
                    async with client.stream(
                        "POST", self.endpoint, json=payload, headers=headers
                    ) as response:
                        if response.status_code >= 400:
                            if self._should_retry(response.status_code, None) and attempt <= self.max_retries:
                                await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
                                continue
                            error_body = await response.aread()
                            raise StreamClientError(
                                f"HTTP {response.status_code}: {error_body.decode('utf-8', errors='replace')}"
                            )

                        yield AgentEvent(AgentEventType.MESSAGE_START)

                        accumulated_content: List[str] = []
                        accumulated_tools: Dict[int, Dict[str, Any]] = {}
                        usage = Usage()

                        async for raw_line in response.aiter_lines():
                            if cancellation_token and cancellation_token.is_set():
                                break

                            line = raw_line.strip()
                            if not line or not line.startswith("data: "):
                                continue

                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                break

                            try:
                                chunk = json.loads(data_str)
                            except json.JSONDecodeError:
                                continue

                            if "usage" in chunk and chunk["usage"]:
                                u = chunk["usage"]
                                usage = Usage(
                                    prompt_tokens=u.get("prompt_tokens", 0),
                                    completion_tokens=u.get("completion_tokens", 0),
                                    total_tokens=u.get("total_tokens", 0),
                                )

                            choices = chunk.get("choices", [])
                            if not choices:
                                continue

                            delta = choices[0].get("delta", {})

                            # 1. Text Delta
                            content_delta = delta.get("content")
                            if content_delta:
                                accumulated_content.append(content_delta)
                                yield AgentEvent(
                                    AgentEventType.MESSAGE_DELTA,
                                    {"delta": content_delta},
                                )

                            # 2. Tool Calls Delta
                            tool_calls_delta = delta.get("tool_calls")
                            if tool_calls_delta:
                                for tc in tool_calls_delta:
                                    idx = tc.get("index", 0)
                                    if idx not in accumulated_tools:
                                        accumulated_tools[idx] = {
                                            "id": tc.get("id", ""),
                                            "name": tc.get("function", {}).get("name", ""),
                                            "arguments": "",
                                        }
                                    if tc.get("id"):
                                        accumulated_tools[idx]["id"] = tc["id"]
                                    fn = tc.get("function", {})
                                    if fn.get("name"):
                                        accumulated_tools[idx]["name"] = fn["name"]
                                    if fn.get("arguments"):
                                        accumulated_tools[idx]["arguments"] += fn["arguments"]

                        # Assemble final assistant message
                        full_content = "".join(accumulated_content) if accumulated_content else None
                        final_tool_calls: Optional[List[ToolCall]] = None
                        if accumulated_tools:
                            final_tool_calls = []
                            for idx in sorted(accumulated_tools.keys()):
                                t_info = accumulated_tools[idx]
                                raw_args = t_info["arguments"]
                                try:
                                    parsed_args = json.loads(raw_args) if raw_args else {}
                                except json.JSONDecodeError:
                                    parsed_args = {"_raw": raw_args}
                                final_tool_calls.append(
                                    ToolCall(
                                        id=t_info["id"] or f"call_{idx}",
                                        name=t_info["name"],
                                        arguments=parsed_args,
                                    )
                                )

                        final_message = AgentMessage(
                            role=Role.ASSISTANT,
                            content=full_content,
                            tool_calls=final_tool_calls,
                            metadata={"usage": usage},
                        )

                        yield AgentEvent(
                            AgentEventType.MESSAGE_END,
                            {"message": final_message},
                        )
                        return

            except (httpx.NetworkError, httpx.TimeoutException) as exc:
                if attempt <= self.max_retries:
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
                    continue
                raise StreamClientError(f"Streaming network error: {exc}") from exc
