"""
Tests for AskQuestionTool and GenerationWorker PySide6 Desktop Signal Bridge.
"""

import asyncio
from typing import Any, Dict
import pytest
from pytestqt.qtbot import QtBot

from apps.atbmind_desktop.workers import GenerationWorker
from atbmind_core.runtime.event_bus import (
    AsyncEventBus,
    AskQuestionEvent,
    SubagentLifecycleEvent,
    TaskOutputEvent,
    TaskStatusChangedEvent,
)
from atbmind_core.runtime.tools.interaction_tools import AskQuestionTool, QuestionSpec


@pytest.mark.asyncio
async def test_generation_worker_bridges_runtime_events(qtbot: QtBot):
    """Verifies that GenerationWorker direct bridge methods emit corresponding Qt signals."""
    worker = GenerationWorker(session_id="test-session", user_input="hello")
    subagent_states = []
    task_outputs = []
    task_completions = []
    questions_received = []

    worker.sig_subagent_state.connect(lambda s_id, st, det: subagent_states.append((s_id, st, det)))
    worker.sig_task_output.connect(lambda t_id, chunk: task_outputs.append((t_id, chunk)))
    worker.sig_task_completed.connect(lambda t_id, code, sumry: task_completions.append((t_id, code, sumry)))
    worker.sig_ask_question.connect(lambda q_data, fut: questions_received.append((q_data, fut)))

    # 1. Subagent event bridge
    worker.bridge_subagent_event(
        SubagentLifecycleEvent(source_id="sub-1", subagent_id="sub-1", state="running", detail="working")
    )
    assert len(subagent_states) == 1
    assert subagent_states[0] == ("sub-1", "running", "working")

    # 2. Task output event bridge
    worker.bridge_task_output_event(
        TaskOutputEvent(source_id="task-10", chunk="compiling assets...\n", stream="stdout")
    )
    assert len(task_outputs) == 1
    assert task_outputs[0] == ("task-10", "compiling assets...\n")

    # 3. Task status event bridge
    worker.bridge_task_status_event(
        TaskStatusChangedEvent(source_id="task-10", new_status="done", exit_code=0, summary="Build finished successfully")
    )
    assert len(task_completions) == 1
    assert task_completions[0] == ("task-10", 0, "Build finished successfully")

    # 4. Ask question event bridge
    loop = asyncio.get_running_loop()
    dummy_fut = loop.create_future()
    worker.bridge_ask_question_event(
        AskQuestionEvent(
            source_id="agent-main",
            questions=[{"question": "Proceed with deployment?", "options": ["Yes", "No"]}],
            future=dummy_fut,
        )
    )
    assert len(questions_received) == 1
    q_dict, fut = questions_received[0]
    assert fut is dummy_fut
    assert len(q_dict["questions"]) == 1


@pytest.mark.asyncio
async def test_generation_worker_event_bus_subscription(qtbot: QtBot):
    """Verifies that GenerationWorker attaches to AsyncEventBus and bridges published events."""
    bus = AsyncEventBus()
    worker = GenerationWorker(session_id="bus-session", prompt="test", event_bus=bus)

    emitted_subagent = []
    emitted_tasks = []

    worker.sig_subagent_state.connect(lambda sid, st, det: emitted_subagent.append((sid, st)))
    worker.sig_task_output.connect(lambda tid, ch: emitted_tasks.append((tid, ch)))

    # Publish on event bus
    await bus.publish(SubagentLifecycleEvent(subagent_id="sub-42", state="idle", detail="ready"))
    await bus.publish(TaskOutputEvent(source_id="task-99", chunk="data-chunk"))

    assert len(emitted_subagent) == 1
    assert emitted_subagent[0] == ("sub-42", "idle")
    assert len(emitted_tasks) == 1
    assert emitted_tasks[0] == ("task-99", "data-chunk")

    # Detach runtime and verify no more events are bridged
    worker.detach_runtime()
    await bus.publish(SubagentLifecycleEvent(subagent_id="sub-43", state="running"))
    assert len(emitted_subagent) == 1


@pytest.mark.asyncio
async def test_ask_question_tool_fallback_mode():
    """Verifies that AskQuestionTool defaults to sensible fallback answers when no handler is configured."""
    tool = AskQuestionTool()
    assert tool.name == "ask_question"

    args = {
        "questions": [
            {
                "question": "Which theme do you prefer?",
                "options": ["(Recommended) Dark Mode", "Light Mode", "System Default"],
                "is_multi_select": False,
            },
            {
                "question": "Enable analytics?",
                "options": ["No", "Yes"],
                "is_multi_select": False,
            },
        ],
        "toolAction": "Configuring preferences",
        "toolSummary": "Theme Selection",
    }

    result = await tool.execute(args)
    assert not result.is_error
    assert "Dark Mode" in result.content
    assert result.metadata.get("fallback") is True


@pytest.mark.asyncio
async def test_ask_question_tool_custom_handler():
    """Verifies that AskQuestionTool invokes custom question handler if provided."""
    async def mock_handler(question_data, future):
        # Simulate user answering the prompt
        future.set_result({"question_1": "System Default"})

    tool = AskQuestionTool(handler=mock_handler)
    args = {
        "questions": [
            {
                "question": "Which theme?",
                "options": ["Dark", "Light", "System Default"],
            }
        ]
    }
    result = await tool.execute(args)
    assert not result.is_error
    assert "System Default" in result.content
    assert result.metadata.get("answers") == {"question_1": "System Default"}


@pytest.mark.asyncio
async def test_ask_question_tool_event_bus_desktop_flow(qtbot: QtBot):
    """Full roundtrip test: tool publishes AskQuestionEvent -> Worker emits sig_ask_question -> slot sets future -> tool resumes."""
    bus = AsyncEventBus()
    worker = GenerationWorker(session_id="bridge-test", user_input="ask user")
    worker.attach_runtime(bus)

    tool = AskQuestionTool(event_bus=bus)

    def on_ask_question(q_dict, fut):
        # UI responds to user
        fut.set_result({"selected": q_dict["questions"][0]["options"][0]})

    worker.sig_ask_question.connect(on_ask_question)

    args = {
        "questions": [
            {
                "question": "Select target platform",
                "options": ["macOS", "Linux", "Windows"],
                "is_multi_select": False,
            }
        ],
        "toolAction": "Selecting platform",
        "toolSummary": "Target Platform",
    }

    result = await tool.execute(args)
    assert not result.is_error
    assert "macOS" in result.content
    assert result.metadata.get("answers") == {"selected": "macOS"}


@pytest.mark.asyncio
async def test_ask_question_tool_timeout():
    """Verifies that AskQuestionTool times out if user does not answer within timeout period."""
    bus = AsyncEventBus()
    tool = AskQuestionTool(event_bus=bus, timeout=0.05)

    args = {
        "questions": [
            {
                "question": "Will you answer?",
                "options": ["Yes", "No"],
            }
        ]
    }

    result = await tool.execute(args)
    assert result.is_error
    assert "timed out" in result.content.lower()


def test_generation_worker_preserved_signals_and_stop():
    """Verifies preserved signals and stop cascade in GenerationWorker."""
    worker = GenerationWorker(session_id="sig-test", prompt="echo test")
    
    tokens = []
    errors = []
    finishes = []
    
    worker.sig_token.connect(lambda s_id, t: tokens.append((s_id, t)))
    worker.sig_error.connect(lambda s_id, err: errors.append((s_id, err)))
    worker.sig_finished.connect(lambda s_id, out: finishes.append((s_id, out)))

    # Emit legacy signals
    worker.token_received.emit("sig-test", "tok1")
    assert len(tokens) == 1
    assert tokens[0] == ("sig-test", "tok1")

    worker.failed.emit("sig-test", "err1")
    assert len(errors) == 1
    assert errors[0] == ("sig-test", "err1")

    worker.text_finished.emit("sig-test", "done1")
    assert len(finishes) == 1
    assert finishes[0] == ("sig-test", "done1")

    worker.stop()
    assert worker._is_cancelled is True


def test_ask_question_tool_openai_schema():
    """Verifies that AskQuestionTool generates valid OpenAI function calling schema."""
    tool = AskQuestionTool()
    schema = tool.to_openai_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "ask_question"
    assert "parameters" in schema["function"]
    assert "questions" in schema["function"]["parameters"]["properties"]


@pytest.mark.asyncio
async def test_ask_question_invalid_arguments():
    """Verifies that invalid arguments return error ToolResult."""
    tool = AskQuestionTool()
    # Missing required 'questions' parameter
    result = await tool.execute({"invalid_param": 123})
    assert result.is_error
    assert "Invalid arguments" in result.content


@pytest.mark.asyncio
async def test_ask_question_mock_response():
    """Verifies that pre-configured mock_response is returned immediately."""
    tool = AskQuestionTool(mock_response={"selected": "Option B"})
    result = await tool.execute({
        "questions": [{"question": "Choose?", "options": ["Option A", "Option B"]}]
    })
    assert not result.is_error
    assert "Option B" in result.content
    assert result.metadata.get("mock") is True


@pytest.mark.asyncio
async def test_ask_question_sync_handler():
    """Verifies that a synchronous 1-argument handler works seamlessly."""
    def sync_handler(data):
        return {"choice": "Sync Option"}

    tool = AskQuestionTool(handler=sync_handler)
    result = await tool.execute({
        "questions": [{"question": "Choose?", "options": ["Sync Option", "Other"]}]
    })
    assert not result.is_error
    assert "Sync Option" in result.content


@pytest.mark.asyncio
async def test_ask_question_cancelled():
    """Verifies that cancelling future returns is_error ToolResult."""
    async def cancelling_handler(data, future):
        future.cancel()

    tool = AskQuestionTool(handler=cancelling_handler)
    result = await tool.execute({
        "questions": [{"question": "Choose?", "options": ["A", "B"]}]
    })
    assert result.is_error
    assert "cancelled" in result.content.lower()
