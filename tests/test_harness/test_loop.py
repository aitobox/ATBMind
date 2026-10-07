import asyncio
import pytest
from atbmind_core.harness.types import (
    Role,
    ToolCall,
    AgentMessage,
    AgentEventType,
    AgentEvent,
)
from atbmind_core.harness.tools.base import AgentTool, ExecutionMode, ToolResult
from atbmind_core.harness.loop import (
    AgentContext,
    AgentLoopConfig,
    agent_loop,
)
from pydantic import BaseModel, Field

# Mock Tools for testing
class AddInput(BaseModel):
    a: int = Field(..., description="First number")
    b: int = Field(..., description="Second number")

class AddTool(AgentTool):
    name = "add"
    description = "Add two numbers"
    parameters_schema = AddInput
    execution_mode = ExecutionMode.PARALLEL

    async def execute(self, args, context=None):
        return ToolResult(content=str(args["a"] + args["b"]))

class StopInput(BaseModel):
    pass

class StopTool(AgentTool):
    name = "stop_now"
    description = "Stop immediately"
    parameters_schema = StopInput
    execution_mode = ExecutionMode.SEQUENTIAL

    async def execute(self, args, context=None):
        return ToolResult(content="Stopped", terminate=True)

# Mock StreamClient
class MockStreamClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.call_count = 0

    async def stream_chat(self, messages, tools=None, system_prompt=None, temperature=None, cancellation_token=None):
        resp = self.responses[self.call_count]
        self.call_count += 1

        yield AgentEvent(AgentEventType.MESSAGE_START)
        if resp.content:
            yield AgentEvent(AgentEventType.MESSAGE_DELTA, {"delta": resp.content})
        yield AgentEvent(AgentEventType.MESSAGE_END, {"message": resp})

def test_loop_simple_text_response():
    async def _run():
        assistant_resp = AgentMessage(role=Role.ASSISTANT, content="Hello there!")
        client = MockStreamClient([assistant_resp])

        ctx = AgentContext(messages=[])
        cfg = AgentLoopConfig(stream_client=client)

        prompts = [AgentMessage(role=Role.USER, content="Hi")]
        events = []
        async for event in agent_loop(prompts, ctx, cfg):
            events.append(event)

        event_types = [e.type for e in events]
        assert event_types[0] == AgentEventType.AGENT_START
        assert AgentEventType.TURN_START in event_types
        assert AgentEventType.MESSAGE_DELTA in event_types
        assert AgentEventType.TURN_END in event_types
        assert event_types[-1] == AgentEventType.AGENT_END

        assert len(ctx.messages) == 2
        assert ctx.messages[0].content == "Hi"
        assert ctx.messages[1].content == "Hello there!"

    asyncio.run(_run())

def test_loop_tool_execution_multi_turn():
    async def _run():
        # Turn 1 calls tool 'add(1, 2)'
        turn1_resp = AgentMessage(
            role=Role.ASSISTANT,
            content="Let me calculate that.",
            tool_calls=[ToolCall(id="call_add_1", name="add", arguments={"a": 1, "b": 2})],
        )
        # Turn 2 sees result '3' and gives final answer
        turn2_resp = AgentMessage(
            role=Role.ASSISTANT,
            content="The answer is 3.",
        )
        client = MockStreamClient([turn1_resp, turn2_resp])

        ctx = AgentContext(messages=[], tools=[AddTool()])
        cfg = AgentLoopConfig(stream_client=client)

        prompts = [AgentMessage(role=Role.USER, content="What is 1 + 2?")]
        events = []
        async for event in agent_loop(prompts, ctx, cfg):
            events.append(event)

        event_types = [e.type for e in events]
        assert AgentEventType.TOOL_CALL_START in event_types
        assert AgentEventType.TOOL_CALL_END in event_types

        # Check that tool result was added to context
        tool_msgs = [m for m in ctx.messages if m.role == Role.TOOL]
        assert len(tool_msgs) == 1
        assert tool_msgs[0].content == "3"
        assert tool_msgs[0].tool_call_id == "call_add_1"

        # Final message is in context
        assert ctx.messages[-1].content == "The answer is 3."

    asyncio.run(_run())

def test_loop_terminate_tool():
    async def _run():
        turn1_resp = AgentMessage(
            role=Role.ASSISTANT,
            tool_calls=[ToolCall(id="call_stop", name="stop_now", arguments={})],
        )
        client = MockStreamClient([turn1_resp])

        ctx = AgentContext(messages=[], tools=[StopTool()])
        cfg = AgentLoopConfig(stream_client=client)

        prompts = [AgentMessage(role=Role.USER, content="Do stop")]
        events = []
        async for event in agent_loop(prompts, ctx, cfg):
            events.append(event)

        # Loop terminates immediately after stop tool without a 2nd turn
        assert client.call_count == 1
        assert events[-1].type == AgentEventType.AGENT_END

    asyncio.run(_run())

def test_loop_before_tool_call_block():
    async def _run():
        turn1_resp = AgentMessage(
            role=Role.ASSISTANT,
            tool_calls=[ToolCall(id="call_blocked", name="add", arguments={"a": 10, "b": 20})],
        )
        turn2_resp = AgentMessage(role=Role.ASSISTANT, content="Understood, blocked.")
        client = MockStreamClient([turn1_resp, turn2_resp])

        async def before_hook(ctx, tc):
            return {"block": True, "reason": "Permission denied by admin", "terminate": False}

        ctx = AgentContext(messages=[], tools=[AddTool()])
        cfg = AgentLoopConfig(stream_client=client, before_tool_call=before_hook)

        prompts = [AgentMessage(role=Role.USER, content="Calculate")]
        events = []
        async for event in agent_loop(prompts, ctx, cfg):
            events.append(event)

        tool_msgs = [m for m in ctx.messages if m.role == Role.TOOL]
        assert len(tool_msgs) == 1
        assert "Permission denied by admin" in tool_msgs[0].content

    asyncio.run(_run())

def test_loop_steering_message_injection():
    async def _run():
        turn1_resp = AgentMessage(
            role=Role.ASSISTANT,
            content="Thinking...",
            tool_calls=[ToolCall(id="call_1", name="add", arguments={"a": 5, "b": 5})],
        )
        turn2_resp = AgentMessage(role=Role.ASSISTANT, content="Adjusted based on steering.")
        client = MockStreamClient([turn1_resp, turn2_resp])

        steering_queue = [AgentMessage(role=Role.USER, content="Wait, use a different formula!")]

        async def get_steering():
            if steering_queue:
                return [steering_queue.pop(0)]
            return []

        ctx = AgentContext(messages=[], tools=[AddTool()])
        cfg = AgentLoopConfig(stream_client=client, get_steering_messages=get_steering)

        prompts = [AgentMessage(role=Role.USER, content="Calculate 5+5")]
        events = []
        async for event in agent_loop(prompts, ctx, cfg):
            events.append(event)

        # Steering message was inserted into context
        contents = [m.content for m in ctx.messages]
        assert "Wait, use a different formula!" in contents

    asyncio.run(_run())

def test_loop_tool_argument_validation_error():
    async def _run():
        # Missing required parameter 'b' for AddTool
        turn1_resp = AgentMessage(
            role=Role.ASSISTANT,
            tool_calls=[ToolCall(id="call_bad", name="add", arguments={"a": 10})],
        )
        turn2_resp = AgentMessage(role=Role.ASSISTANT, content="Handled invalid argument.")
        client = MockStreamClient([turn1_resp, turn2_resp])

        ctx = AgentContext(messages=[], tools=[AddTool()])
        cfg = AgentLoopConfig(stream_client=client)

        prompts = [AgentMessage(role=Role.USER, content="Bad add call")]
        events = []
        async for event in agent_loop(prompts, ctx, cfg):
            events.append(event)

        tool_msgs = [m for m in ctx.messages if m.role == Role.TOOL]
        assert len(tool_msgs) == 1
        assert "Invalid arguments" in tool_msgs[0].content

    asyncio.run(_run())

