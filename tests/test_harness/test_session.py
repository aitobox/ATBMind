import asyncio
import time
import uuid
import pytest
from atbmind_core.harness.types import (
    Role,
    AgentMessage,
    AgentEventType,
    AgentEvent,
)
from atbmind_core.harness.loop import AgentLoopConfig
from atbmind_core.harness.session import AgentSession
from atbmind_core.plugins.schemas import SessionRecord
from atbmind_core.storage.session_store import SessionStore

class MockStreamClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.idx = 0

    async def stream_chat(self, messages, tools=None, system_prompt=None, temperature=None, cancellation_token=None):
        resp = self.responses[self.idx]
        self.idx += 1
        yield AgentEvent(AgentEventType.MESSAGE_START)
        if resp.content:
            yield AgentEvent(AgentEventType.MESSAGE_DELTA, {"delta": resp.content})
        yield AgentEvent(AgentEventType.MESSAGE_END, {"message": resp})

def test_session_prompt_and_sqlite_sync():
    async def _run():
        store = SessionStore(":memory:")
        s_id = str(uuid.uuid4())
        now = time.time()
        record = SessionRecord(
            session_id=s_id,
            title="Test Session",
            created_at=now,
            updated_at=now,
        )
        s_rec = store.create_session(record)

        resp1 = AgentMessage(role=Role.ASSISTANT, content="Hello, I am ready.")
        client = MockStreamClient([resp1])

        session = AgentSession(
            session_id=s_rec.session_id,
            stream_client=client,
            store=store,
        )

        events = []
        async for event in session.prompt("Hi"):
            events.append(event)

        # Context has user and assistant
        assert len(session.messages) == 2
        assert session.messages[0].content == "Hi"
        assert session.messages[1].content == "Hello, I am ready."

        # SQLite store has persisted the messages
        stored_msgs = store.get_messages(s_rec.session_id)
        assert len(stored_msgs) == 2
        assert stored_msgs[0].content == "Hi"
        assert stored_msgs[1].content == "Hello, I am ready."

    asyncio.run(_run())

def test_session_steering():
    async def _run():
        resp1 = AgentMessage(role=Role.ASSISTANT, content="Done")
        client = MockStreamClient([resp1])

        session = AgentSession(
            session_id="test_steering",
            stream_client=client,
        )

        session.send_steering("Don't forget rule 1")
        pending = await session.get_steering_messages()
        assert len(pending) == 1
        assert pending[0].content == "Don't forget rule 1"

    asyncio.run(_run())

def test_session_compaction():
    async def _run():
        session = AgentSession(
            session_id="compaction_test",
            stream_client=MockStreamClient([]),
            max_context_tokens=100,  # very small threshold
        )

        # Inject 10 long messages
        for i in range(10):
            session.messages.append(AgentMessage(role=Role.USER, content=f"Long user prompt #{i} " * 20))
            session.messages.append(AgentMessage(role=Role.ASSISTANT, content=f"Long assistant reply #{i} " * 20))

        initial_len = len(session.messages)
        compacted = session.maybe_compact()
        assert compacted is True
        # Length reduced and summary injected
        assert len(session.messages) < initial_len
        assert any("Conversation Summary" in (m.content or "") for m in session.messages)

    asyncio.run(_run())

def test_session_thread_safe_steering():
    import threading

    session = AgentSession(
        session_id="thread_safe_steering",
        stream_client=MockStreamClient([]),
    )

    def worker_thread(tid):
        for i in range(10):
            session.send_steering(f"msg from thread {tid}-{i}")

    threads = [threading.Thread(target=worker_thread, args=(t,)) for t in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    async def _check():
        msgs = await session.get_steering_messages()
        assert len(msgs) == 50

    asyncio.run(_check())

