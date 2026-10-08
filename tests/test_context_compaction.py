"""Unit tests for ContextCompactionMiddleware and loop integration (Issue #72)."""

from __future__ import annotations

import asyncio
from typing import List
import pytest

from atbmind_core.harness.types import AgentMessage, Role, AgentEvent, AgentEventType
from atbmind_core.harness.loop import AgentContext, AgentLoopConfig, agent_loop
from atbmind_core.harness.middleware.compaction import ContextCompactionMiddleware


def test_compaction_skip_when_under_budget():
    mw = ContextCompactionMiddleware(max_tokens_budget=1000, keep_recent_turns=3)
    messages = [
        AgentMessage(role=Role.SYSTEM, content="System instructions"),
        AgentMessage(role=Role.USER, content="Hello"),
        AgentMessage(role=Role.ASSISTANT, content="Hi there!"),
    ]

    assert not mw.should_compact(messages)


@pytest.mark.asyncio
async def test_compaction_triggered_when_over_budget():
    mw = ContextCompactionMiddleware(max_tokens_budget=100, keep_recent_turns=3)

    # Generate a conversation with 10 long turns
    messages: List[AgentMessage] = [
        AgentMessage(role=Role.SYSTEM, content="You are a helpful coding assistant."),
    ]
    for i in range(10):
        messages.append(AgentMessage(role=Role.USER, content=f"Step {i}: Please analyze the detailed log data " * 5))
        messages.append(AgentMessage(role=Role.ASSISTANT, content=f"Step {i}: Analysis results and recommendations " * 5))

    original_count = len(messages)
    assert original_count == 21
    assert mw.should_compact(messages)

    compacted = await mw.compact(messages)

    # Expect: System prompt + 1 summary message + last 3 recent messages = 5
    assert len(compacted) == 5
    assert compacted[0].role == Role.SYSTEM
    assert compacted[0].content == "You are a helpful coding assistant."

    assert "[Conversation Summary:" in compacted[1].content
    assert compacted[-3].content == messages[-3].content
    assert compacted[-2].content == messages[-2].content
    assert compacted[-1].content == messages[-1].content


@pytest.mark.asyncio
async def test_custom_summarize_fn():
    async def custom_summarizer(msgs: List[AgentMessage]) -> str:
        return f"Custom summary of {len(msgs)} messages."

    mw = ContextCompactionMiddleware(
        max_tokens_budget=50,
        keep_recent_turns=2,
        summarize_fn=custom_summarizer,
    )

    messages = [
        AgentMessage(role=Role.SYSTEM, content="System prompt"),
        AgentMessage(role=Role.USER, content="Message 1 " * 10),
        AgentMessage(role=Role.ASSISTANT, content="Response 1 " * 10),
        AgentMessage(role=Role.USER, content="Message 2 " * 10),
        AgentMessage(role=Role.ASSISTANT, content="Response 2 " * 10),
        AgentMessage(role=Role.USER, content="Recent question"),
        AgentMessage(role=Role.ASSISTANT, content="Recent answer"),
    ]

    compacted = await mw.compact(messages)
    assert len(compacted) == 4
    assert "Custom summary of 4 messages." in compacted[1].content


@pytest.mark.asyncio
async def test_loop_integration_with_compaction_middleware():
    class MockStreamClient:
        async def stream_chat(self, messages, tools=None, system_prompt=None, temperature=None, cancellation_token=None):
            yield AgentEvent(AgentEventType.TOKEN, {"delta": "Hello from mock"})
            yield AgentEvent(AgentEventType.MESSAGE_END, {
                "message": AgentMessage(role=Role.ASSISTANT, content="Hello from mock")
            })

    mw = ContextCompactionMiddleware(max_tokens_budget=50, keep_recent_turns=2)
    context = AgentContext(
        messages=[
            AgentMessage(role=Role.SYSTEM, content="System prompt"),
            AgentMessage(role=Role.USER, content="Long user request " * 10),
            AgentMessage(role=Role.ASSISTANT, content="Long assistant response " * 10),
            AgentMessage(role=Role.USER, content="Another request " * 10),
            AgentMessage(role=Role.ASSISTANT, content="Another response " * 10),
        ]
    )

    config = AgentLoopConfig(
        stream_client=MockStreamClient(),
        middlewares=[mw],
        max_turns=1,
    )

    events = []
    async for event in agent_loop(prompts=[], context=context, config=config):
        events.append(event)

    # Context messages must have been compacted prior to or during the loop
    assert any("[Conversation Summary:" in (m.content or "") for m in context.messages)
