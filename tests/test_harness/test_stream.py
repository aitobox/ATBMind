import asyncio
import json
import pytest
import httpx
from atbmind_core.harness.types import (
    Role,
    AgentMessage,
    AgentEventType,
    AgentEvent,
)
from atbmind_core.harness.stream import StreamClient

def test_stream_text_deltas():
    async def _run():
        sse_lines = [
            'data: {"choices": [{"delta": {"content": "Hello"}}]}\n\n',
            'data: {"choices": [{"delta": {"content": " world!"}}]}\n\n',
            'data: {"choices": [{"delta": {}}], "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7}}\n\n',
            'data: [DONE]\n\n',
        ]

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            async def response_stream():
                for line in sse_lines:
                    yield line.encode("utf-8")
            return httpx.Response(200, content=response_stream())

        transport = httpx.MockTransport(mock_handler)
        client = StreamClient(base_url="https://api.example.com/v1", api_key="sk-test", transport=transport)

        messages = [AgentMessage(role=Role.USER, content="Hi")]
        events = []
        async for event in client.stream_chat(messages):
            events.append(event)

        types = [e.type for e in events]
        assert AgentEventType.MESSAGE_START in types
        assert AgentEventType.MESSAGE_DELTA in types
        assert AgentEventType.MESSAGE_END in types

        deltas = [e.payload["delta"] for e in events if e.type == AgentEventType.MESSAGE_DELTA]
        assert "".join(deltas) == "Hello world!"

        end_event = [e for e in events if e.type == AgentEventType.MESSAGE_END][0]
        final_msg: AgentMessage = end_event.payload["message"]
        assert final_msg.role == Role.ASSISTANT
        assert final_msg.content == "Hello world!"
        assert final_msg.metadata["usage"].total_tokens == 7

    asyncio.run(_run())

def test_stream_fragmented_tool_calls():
    async def _run():
        sse_lines = [
            'data: {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call_abc", "type": "function", "function": {"name": "read_file", "arguments": "{\\"path\\": "}}]}}]}\n\n',
            'data: {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "\\"foo.txt\\"}"}}]}}]}\n\n',
            'data: {"choices": [{"delta": {}}]}\n\n',
            'data: [DONE]\n\n',
        ]

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            async def response_stream():
                for line in sse_lines:
                    yield line.encode("utf-8")
            return httpx.Response(200, content=response_stream())

        transport = httpx.MockTransport(mock_handler)
        client = StreamClient(base_url="https://api.example.com/v1", api_key="sk-test", transport=transport)

        messages = [AgentMessage(role=Role.USER, content="Read foo.txt")]
        events = []
        async for event in client.stream_chat(messages):
            events.append(event)

        end_event = [e for e in events if e.type == AgentEventType.MESSAGE_END][0]
        final_msg: AgentMessage = end_event.payload["message"]
        assert final_msg.tool_calls is not None
        assert len(final_msg.tool_calls) == 1
        tc = final_msg.tool_calls[0]
        assert tc.id == "call_abc"
        assert tc.name == "read_file"
        assert tc.arguments == {"path": "foo.txt"}

    asyncio.run(_run())
