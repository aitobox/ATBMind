"""
ATBMind Pi-Style Harness Core Types
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Dict, List, Optional, Union

class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]

@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

@dataclass
class AgentMessage:
    role: Role
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_llm_dict(self) -> Dict[str, Any]:
        """Serializes to an OpenAI-compatible message dict without internal metadata."""
        msg: Dict[str, Any] = {"role": self.role.value}
        if self.content is not None:
            msg["content"] = self.content
        if self.tool_calls is not None:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, ensure_ascii=False)
                        if isinstance(tc.arguments, dict)
                        else str(tc.arguments),
                    },
                }
                for tc in self.tool_calls
            ]
        if self.tool_call_id is not None:
            msg["tool_call_id"] = self.tool_call_id
        if self.name is not None:
            msg["name"] = self.name
        return msg

    @classmethod
    def from_llm_dict(cls, data: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> AgentMessage:
        """Constructs an AgentMessage from an OpenAI-compatible dictionary."""
        role = Role(data.get("role", "user"))
        content = data.get("content")
        tool_call_id = data.get("tool_call_id")
        name = data.get("name")

        tool_calls: Optional[List[ToolCall]] = None
        raw_tool_calls = data.get("tool_calls")
        if raw_tool_calls:
            tool_calls = []
            for rtc in raw_tool_calls:
                fn = rtc.get("function", {})
                fn_name = fn.get("name", "")
                raw_args = fn.get("arguments", "{}")
                if isinstance(raw_args, str):
                    try:
                        args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        args = {"_raw": raw_args}
                else:
                    args = raw_args
                tool_calls.append(ToolCall(id=rtc.get("id", ""), name=fn_name, arguments=args))

        return cls(
            role=role,
            content=content,
            tool_calls=tool_calls,
            tool_call_id=tool_call_id,
            name=name,
            metadata=metadata or {},
        )

class AgentEventType(StrEnum):
    AGENT_START = "agent_start"
    TURN_START = "turn_start"
    MESSAGE_START = "message_start"
    MESSAGE_DELTA = "message_delta"
    MESSAGE_END = "message_end"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_DELTA = "tool_call_delta"
    TOOL_CALL_END = "tool_call_end"
    TURN_END = "turn_end"
    AGENT_END = "agent_end"

@dataclass
class AgentEvent:
    type: AgentEventType
    payload: Dict[str, Any] = field(default_factory=dict)
