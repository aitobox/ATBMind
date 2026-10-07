"""
Tests for QuestionCardWidget, cascading teardown, cron Sunday range normalization,
and core_tools skill mounting.
"""

import asyncio
from datetime import datetime
from pathlib import Path
import pytest
from pytestqt.qtbot import QtBot

from atbmind_core.runtime.event_bus import AsyncEventBus
from atbmind_core.runtime.tasks import TaskManager, parse_cron_field, get_next_cron_run
from atbmind_core.runtime.subagents import SubagentOrchestrator, SubagentState
from atbmind_core.skills.loader import SkillLoader
from apps.atbmind_desktop.widgets.question_card import QuestionCardItem
from apps.atbmind_desktop.widgets.chat_stream import ChatStreamView
from apps.atbmind_desktop.workers import GenerationWorker


def test_cron_sunday_range_normalization():
    """Verify that day-of-week cron range 5-7 includes Sunday (0)."""
    dow_set = parse_cron_field("5-7", 0, 6)
    assert 5 in dow_set
    assert 6 in dow_set
    assert 0 in dow_set

    # Test single 7
    dow_single = parse_cron_field("7", 0, 6)
    assert dow_single == {0}

    # Test get_next_cron_run
    base = datetime(2026, 10, 7, 12, 0, 0)
    next_run = get_next_cron_run("0 14 * * *", base_time=base)
    assert next_run.hour == 14
    assert next_run.minute == 0


@pytest.mark.asyncio
async def test_subagent_send_message_rejects_canceling(tmp_path: Path):
    """Verify that send_message rejects enqueuing to agents in CANCELING state."""
    bus = AsyncEventBus()
    orch = SubagentOrchestrator(event_bus=bus, transcript_dir=tmp_path)
    sub_id = await orch.spawn_subagent("research", "Researcher", "Find info")

    inst = orch.get_instance(sub_id)
    assert inst is not None
    inst.state = SubagentState.CANCELING

    res = await orch.send_message(sub_id, "Hello while canceling")
    assert res is False
    await orch.shutdown()


def test_core_tools_skill_loading():
    """Verify that skills/core_tools loads all 11 Antigravity tools."""
    skill = SkillLoader.load_from_dir("skills/core_tools")
    assert skill.metadata.name == "core_tools"
    assert len(skill.tools) == 11
    tool_names = {t.name for t in skill.tools}
    expected_tools = {
        "view_file",
        "write_to_file",
        "replace_file_content",
        "run_command",
        "manage_task",
        "schedule",
        "invoke_subagent",
        "send_message",
        "manage_subagents",
        "define_subagent",
        "ask_question",
    }
    assert expected_tools.issubset(tool_names)


def test_question_card_widget_flow(qtbot: QtBot):
    """Test inline QuestionCardItem rendering, selection, and future resolution."""
    loop = asyncio.new_event_loop()
    future = loop.create_future()

    q_data = {
        "questions": [
            {
                "question": "Which architecture pattern to adopt?",
                "options": ["(Recommended) Option A", "Option B", "Option C"],
                "is_multi_select": False,
            }
        ],
        "tool_action": "Choosing architecture",
    }

    card = QuestionCardItem(question_data=q_data, response_future=future)
    qtbot.addWidget(card)

    received_answers = []
    card.submitted.connect(lambda ans: received_answers.append(ans))

    # Pre-selected recommended option
    assert card.submit_btn.isEnabled()
    card.submit_btn.click()

    assert len(received_answers) == 1
    assert "(Recommended) Option A" in received_answers[0]
    assert card._is_submitted is True
    assert not card.submit_btn.isEnabled()
    assert future.done()
    assert future.result() == received_answers[0]
    loop.close()


def test_chat_stream_add_question_card(qtbot: QtBot):
    """Test ChatStreamView integration with QuestionCardItem."""
    view = ChatStreamView()
    qtbot.addWidget(view)

    view.add_loading_indicator("Thinking...")
    assert view.has_loading_indicator()

    q_data = {
        "questions": [
            {
                "question": "Are you sure?",
                "options": ["Yes", "No"],
                "is_multi_select": False,
            }
        ]
    }
    card = view.add_question_card(q_data)
    # Adding card removes loading indicator
    assert not view.has_loading_indicator()
    assert isinstance(card, QuestionCardItem)


def test_generation_worker_stop_cascades(tmp_path: Path):
    """Test that GenerationWorker.stop() calls shutdown on attached task_manager and orchestrator."""
    bus = AsyncEventBus()
    tm = TaskManager(event_bus=bus, log_dir=tmp_path)
    orch = SubagentOrchestrator(event_bus=bus, transcript_dir=tmp_path)

    worker = GenerationWorker(
        session_id="test-stop",
        user_input="test",
        event_bus=bus,
        task_manager=tm,
        orchestrator=orch,
    )

    worker.stop()
    assert worker._is_cancelled is True
