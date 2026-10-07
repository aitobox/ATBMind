import asyncio
import os
import tempfile
import time
import uuid
import pytest

from atbmind_core.harness.types import (
    Role,
    ToolCall,
    AgentMessage,
    AgentEventType,
    AgentEvent,
)
from atbmind_core.harness.session import AgentSession
from atbmind_core.harness.tools import (
    GenerateImageTool,
    WriteFileTool,
    ReadFileTool,
)
from atbmind_core.plugins.schemas import SessionRecord
from atbmind_core.storage.session_store import SessionStore

class MockE2EStreamClient:
    def __init__(self, turns):
        self.turns = list(turns)
        self.idx = 0

    async def stream_chat(self, messages, tools=None, system_prompt=None, temperature=None, cancellation_token=None):
        resp = self.turns[self.idx]
        self.idx += 1
        yield AgentEvent(AgentEventType.MESSAGE_START)
        if resp.content:
            yield AgentEvent(AgentEventType.MESSAGE_DELTA, {"delta": resp.content})
        yield AgentEvent(AgentEventType.MESSAGE_END, {"message": resp})

def test_end_to_end_multi_tool_workflow():
    async def _run():
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SessionStore(":memory:")
            s_id = str(uuid.uuid4())
            now = time.time()
            store.create_session(
                SessionRecord(session_id=s_id, title="E2E Session", created_at=now, updated_at=now)
            )

            log_path = os.path.join(tmpdir, "generation.log")

            # Turn 1: Model calls generate_image and write_file
            t1_tool_calls = [
                ToolCall(
                    id="tc_gen",
                    name="generate_image",
                    arguments={"prompt": "A futuristic city in mist", "style": "cyberpunk"},
                ),
                ToolCall(
                    id="tc_write",
                    name="write_file",
                    arguments={"path": log_path, "content": "Generation started at 2026-10-07"},
                ),
            ]
            t1_resp = AgentMessage(
                role=Role.ASSISTANT,
                content="Generating the image and writing the log...",
                tool_calls=t1_tool_calls,
            )

            # Turn 2: Model wraps up
            t2_resp = AgentMessage(
                role=Role.ASSISTANT,
                content="Task completed: image rendered and log recorded.",
            )

            client = MockE2EStreamClient([t1_resp, t2_resp])
            tools = [GenerateImageTool(), WriteFileTool(), ReadFileTool()]

            session = AgentSession(
                session_id=s_id,
                stream_client=client,
                tools=tools,
                store=store,
            )

            events = []
            async for ev in session.prompt("Generate image and write log"):
                events.append(ev)

            # Assert event lifecycle was completely emitted
            types = [e.type for e in events]
            assert AgentEventType.AGENT_START in types
            assert AgentEventType.TOOL_CALL_START in types
            assert AgentEventType.TOOL_CALL_END in types
            assert AgentEventType.AGENT_END in types

            # Check that log file was actually written by the WriteFileTool
            assert os.path.exists(log_path)
            with open(log_path, "r", encoding="utf-8") as f:
                assert "Generation started at 2026-10-07" in f.read()

            # Check SQLite persistence
            saved_messages = store.get_messages(s_id)
            # user + assistant(tools) + 2 tool results + final assistant
            assert len(saved_messages) == 5
            roles = [m.role for m in saved_messages]
            assert roles == ["user", "assistant", "tool", "tool", "assistant"]

    asyncio.run(_run())
