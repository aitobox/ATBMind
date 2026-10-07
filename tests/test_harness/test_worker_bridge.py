import time
import pytest
from PySide6.QtCore import QCoreApplication
from apps.atbmind_desktop.workers import GenerationWorker
from atbmind_core.harness.types import (
    Role,
    ToolCall,
    AgentMessage,
    AgentEventType,
    AgentEvent,
)

class MockStreamClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.idx = 0

    async def stream_chat(self, messages, tools=None, system_prompt=None, temperature=None, cancellation_token=None):
        resp = self.responses[self.idx]
        self.idx += 1
        yield AgentEvent(AgentEventType.MESSAGE_START)
        if resp.content:
            for ch in resp.content.split():
                yield AgentEvent(AgentEventType.MESSAGE_DELTA, {"delta": ch + " "})
        yield AgentEvent(AgentEventType.MESSAGE_END, {"message": resp})

def test_generation_worker_harness_stream(qtbot):
    resp = AgentMessage(role=Role.ASSISTANT, content="Hello streamed world")
    mock_client = MockStreamClient([resp])

    worker = GenerationWorker(
        session_id="test_worker_session",
        prompt="Tell me a story",
        llm_client=mock_client,
        use_harness=True,
    )

    tokens = []
    finished_text = []

    worker.token_received.connect(lambda s_id, delta: tokens.append(delta))
    worker.text_finished.connect(lambda s_id, text: finished_text.append(text))

    with qtbot.waitSignal(worker.text_finished, timeout=5000):
        worker.start()

    worker.wait(2000)

    assert "".join(tokens).strip() == "Hello streamed world"
    assert len(finished_text) == 1
    assert finished_text[0].strip() == "Hello streamed world"

def test_generation_worker_cancellation(qtbot):
    class SlowStreamClient:
        async def stream_chat(self, messages, tools=None, system_prompt=None, temperature=None, cancellation_token=None):
            yield AgentEvent(AgentEventType.MESSAGE_START)
            for i in range(100):
                if cancellation_token and cancellation_token.is_set():
                    break
                yield AgentEvent(AgentEventType.MESSAGE_DELTA, {"delta": f"chunk{i} "})
                import asyncio
                await asyncio.sleep(0.05)
            yield AgentEvent(AgentEventType.MESSAGE_END, {"message": AgentMessage(role=Role.ASSISTANT, content="done")})

    worker = GenerationWorker(
        session_id="test_cancel_sess",
        prompt="Slow generation",
        llm_client=SlowStreamClient(),
        use_harness=True,
    )

    worker.start()
    time.sleep(0.1)
    worker.cancel()
    worker.wait(2000)

    assert not worker.isRunning()

