import json
import pytest
from atbmind_core.harness.types import (
    Role,
    ToolCall,
    AgentMessage,
    AgentEventType,
    AgentEvent,
    Usage,
)

def test_agent_message_user_conversion():
    msg = AgentMessage(role=Role.USER, content="Hello, world!")
    llm_dict = msg.to_llm_dict()
    assert llm_dict == {"role": "user", "content": "Hello, world!"}

def test_agent_message_with_tool_calls():
    tool_call = ToolCall(id="call_123", name="bash", arguments={"command": "ls -la"})
    msg = AgentMessage(
        role=Role.ASSISTANT,
        content="Running command...",
        tool_calls=[tool_call],
        metadata={"ui_badge": "running"},
    )
    llm_dict = msg.to_llm_dict()
    assert llm_dict["role"] == "assistant"
    assert llm_dict["content"] == "Running command..."
    assert len(llm_dict["tool_calls"]) == 1
    assert llm_dict["tool_calls"][0]["id"] == "call_123"
    assert llm_dict["tool_calls"][0]["type"] == "function"
    assert llm_dict["tool_calls"][0]["function"]["name"] == "bash"
    assert json.loads(llm_dict["tool_calls"][0]["function"]["arguments"]) == {"command": "ls -la"}
    # metadata should be stripped
    assert "metadata" not in llm_dict

def test_agent_message_tool_result():
    msg = AgentMessage(
        role=Role.TOOL,
        content="total 0",
        tool_call_id="call_123",
        name="bash",
    )
    llm_dict = msg.to_llm_dict()
    assert llm_dict == {
        "role": "tool",
        "content": "total 0",
        "tool_call_id": "call_123",
        "name": "bash",
    }

def test_agent_message_from_llm_dict():
    raw_dict = {
        "role": "assistant",
        "content": "Look at this:",
        "tool_calls": [
            {
                "id": "tc_1",
                "type": "function",
                "function": {
                    "name": "read_file",
                    "arguments": '{"path": "README.md"}',
                },
            }
        ],
    }
    msg = AgentMessage.from_llm_dict(raw_dict)
    assert msg.role == Role.ASSISTANT
    assert msg.content == "Look at this:"
    assert msg.tool_calls is not None
    assert len(msg.tool_calls) == 1
    assert msg.tool_calls[0].name == "read_file"
    assert msg.tool_calls[0].arguments == {"path": "README.md"}

def test_agent_event_structure():
    event = AgentEvent(
        type=AgentEventType.MESSAGE_DELTA,
        payload={"delta": "Hello"},
    )
    assert event.type == AgentEventType.MESSAGE_DELTA
    assert event.payload["delta"] == "Hello"

def test_usage_dataclass():
    usage = Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30)
    assert usage.prompt_tokens == 10
    assert usage.total_tokens == 30
