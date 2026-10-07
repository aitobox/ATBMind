"""
ATBMind Pi-Style Core Agent Loop State Machine
Implements double-loop, steering message injection, parallel/sequential tool dispatching, and hooks.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional

from atbmind_core.harness.stream import StreamClient
from atbmind_core.harness.tools.base import AgentTool, ExecutionMode, ToolResult
from atbmind_core.harness.types import (
    AgentEvent,
    AgentEventType,
    AgentMessage,
    Role,
    ToolCall,
)

logger = logging.getLogger("atbmind.harness.loop")

@dataclass
class AgentContext:
    messages: List[AgentMessage] = field(default_factory=list)
    tools: List[AgentTool] = field(default_factory=list)
    system_prompt: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AgentLoopConfig:
    stream_client: Any  # StreamClient or mock
    model: str = "gpt-4o"
    temperature: Optional[float] = None
    max_turns: int = 25
    before_tool_call: Optional[
        Callable[[AgentContext, ToolCall], Awaitable[Optional[Dict[str, Any]]]]
    ] = None
    after_tool_call: Optional[
        Callable[[AgentContext, ToolCall, ToolResult], Awaitable[Optional[ToolResult]]]
    ] = None
    get_steering_messages: Optional[
        Callable[[], Awaitable[List[AgentMessage]]]
    ] = None

async def agent_loop(
    prompts: List[AgentMessage],
    context: AgentContext,
    config: AgentLoopConfig,
    cancellation_token: Optional[asyncio.Event] = None,
) -> AsyncIterator[AgentEvent]:
    """
    Core Agent Loop generator that yields fine-grained events.
    """
    yield AgentEvent(AgentEventType.AGENT_START)

    # Ingest incoming prompt messages
    for prompt in prompts:
        context.messages.append(prompt)
        yield AgentEvent(AgentEventType.MESSAGE_START, {"message": prompt})
        yield AgentEvent(AgentEventType.MESSAGE_END, {"message": prompt})

    tool_map: Dict[str, AgentTool] = {t.name: t for t in context.tools}
    tool_schemas = [t.to_openai_schema() for t in context.tools] if context.tools else None

    turns_count = 0

    while turns_count < config.max_turns:
        if cancellation_token and cancellation_token.is_set():
            break

        # Check and inject steering messages before each turn
        if config.get_steering_messages:
            try:
                steering_messages = await config.get_steering_messages()
                for sm in steering_messages:
                    context.messages.append(sm)
                    yield AgentEvent(AgentEventType.MESSAGE_START, {"message": sm})
                    yield AgentEvent(AgentEventType.MESSAGE_END, {"message": sm})
            except Exception as e:
                logger.error("Error polling steering messages: %s", e)

        turns_count += 1
        yield AgentEvent(AgentEventType.TURN_START, {"turn_index": turns_count})

        assistant_message: Optional[AgentMessage] = None

        # Stream LLM output
        try:
            async for event in config.stream_client.stream_chat(
                messages=context.messages,
                tools=tool_schemas,
                system_prompt=context.system_prompt,
                temperature=config.temperature,
                cancellation_token=cancellation_token,
            ):
                yield event
                if event.type == AgentEventType.MESSAGE_END:
                    assistant_message = event.payload.get("message")
        except Exception as exc:
            logger.exception("LLM stream failure: %s", exc)
            yield AgentEvent(
                AgentEventType.TURN_END,
                {"error": str(exc), "turn_index": turns_count},
            )
            break

        if assistant_message is None:
            break

        context.messages.append(assistant_message)

        # 1. No tool calls -> Assistant completed plain response
        if not assistant_message.tool_calls:
            yield AgentEvent(
                AgentEventType.TURN_END,
                {"message": assistant_message, "tool_results": []},
            )

            # Check if user injected follow-up/steering during the turn
            pending_steering: List[AgentMessage] = []
            if config.get_steering_messages:
                pending_steering = await config.get_steering_messages()

            if pending_steering:
                for sm in pending_steering:
                    context.messages.append(sm)
                    yield AgentEvent(AgentEventType.MESSAGE_START, {"message": sm})
                    yield AgentEvent(AgentEventType.MESSAGE_END, {"message": sm})
                continue
            else:
                break

        # 2. Assistant requested tool calls
        tool_calls = assistant_message.tool_calls

        for tc in tool_calls:
            yield AgentEvent(
                AgentEventType.TOOL_CALL_START,
                {"tool_call_id": tc.id, "name": tc.name, "arguments": tc.arguments},
            )

        async def execute_single_call(tc: ToolCall) -> ToolResult:
            # Preflight hook
            if config.before_tool_call:
                try:
                    pre_res = await config.before_tool_call(context, tc)
                    if pre_res and pre_res.get("block"):
                        return ToolResult(
                            content=pre_res.get("reason", "Tool execution blocked by policy"),
                            is_error=True,
                            terminate=pre_res.get("terminate", False),
                        )
                except Exception as hook_err:
                    logger.error("Error in before_tool_call hook: %s", hook_err)

            tool = tool_map.get(tc.name)
            if not tool:
                return ToolResult(
                    content=f"Error: Unknown tool '{tc.name}'",
                    is_error=True,
                )

            try:
                res = await tool.execute(tc.arguments, context)
            except Exception as tool_err:
                logger.exception("Tool execution exception: %s", tool_err)
                res = ToolResult(
                    content=f"Error executing tool '{tc.name}': {tool_err}",
                    is_error=True,
                )

            # Post-execution hook
            if config.after_tool_call:
                try:
                    override = await config.after_tool_call(context, tc, res)
                    if override is not None:
                        res = override
                except Exception as post_err:
                    logger.error("Error in after_tool_call hook: %s", post_err)

            return res

        # Check execution mode
        is_sequential = any(
            tool_map.get(tc.name) is not None
            and tool_map[tc.name].execution_mode == ExecutionMode.SEQUENTIAL
            for tc in tool_calls
        )

        executed_results: List[ToolResult] = []
        if is_sequential:
            for tc in tool_calls:
                r = await execute_single_call(tc)
                executed_results.append(r)
        else:
            executed_results = await asyncio.gather(
                *[execute_single_call(tc) for tc in tool_calls]
            )

        # Emit completion events and register tool result messages
        for tc, res in zip(tool_calls, executed_results):
            yield AgentEvent(
                AgentEventType.TOOL_CALL_END,
                {
                    "tool_call_id": tc.id,
                    "name": tc.name,
                    "result": res.content,
                    "is_error": res.is_error,
                    "metadata": res.metadata,
                    "terminate": res.terminate,
                },
            )
            tool_msg = AgentMessage(
                role=Role.TOOL,
                content=res.content,
                tool_call_id=tc.id,
                name=tc.name,
                metadata=res.metadata,
            )
            context.messages.append(tool_msg)
            yield AgentEvent(AgentEventType.MESSAGE_START, {"message": tool_msg})
            yield AgentEvent(AgentEventType.MESSAGE_END, {"message": tool_msg})

        yield AgentEvent(
            AgentEventType.TURN_END,
            {"message": assistant_message, "tool_results": executed_results},
        )

        # Check termination hint
        if executed_results and all(r.terminate for r in executed_results):
            break

    yield AgentEvent(
        AgentEventType.AGENT_END,
        {"messages": context.messages, "turns": turns_count},
    )
