"""
Tests for Composite AgentPromptDock (Task 4).
Validates QueuedMessagesWidget, SubagentRunningBanner, AgentInputCard,
and AgentPromptDock container with signal routing and Antigravity styling.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from apps.atbmind_desktop.widgets.agent_dock import (
    AgentInputCard,
    AgentPromptDock,
    QueuedMessagesWidget,
    SubagentRunningBanner,
)


def test_queued_messages_widget(qtbot):
    w = QueuedMessagesWidget()
    qtbot.addWidget(w)
    assert not w.isVisible()

    w.set_queued_messages(["/grill-me please check code"])
    assert w.isVisible()
    assert w.count() == 1

    with qtbot.waitSignal(w.delete_requested, timeout=1000) as sig:
        w.trigger_delete(0)
    assert sig.args == [0]


def test_subagent_running_banner(qtbot):
    b = SubagentRunningBanner()
    qtbot.addWidget(b)
    assert not b.isVisible()

    b.set_running_subagents([("sub1", "Task 1 Reviewer")])
    assert b.isVisible()
    assert "Task 1 Reviewer" in b.text()


def test_agent_prompt_dock_submission(qtbot):
    dock = AgentPromptDock()
    qtbot.addWidget(dock)

    dock.input_card.set_prompt_text("Hello Agent")
    with qtbot.waitSignal(dock.submit_requested, timeout=1000) as sig:
        dock.input_card.btn_send.click()
    prompt, payload = sig.args
    assert prompt == "Hello Agent"
    assert "model" in payload


def test_queued_messages_widget_actions(qtbot):
    w = QueuedMessagesWidget()
    qtbot.addWidget(w)

    w.set_queued_messages(["Task 1 prompt", "Task 2 prompt"])
    assert w.count() == 2

    # Test send now trigger
    with qtbot.waitSignal(w.send_now_requested, timeout=1000) as sig:
        w.trigger_send_now(0)
    assert sig.args == [0]

    # Test edit trigger
    with qtbot.waitSignal(w.edit_requested, timeout=1000) as sig:
        w.trigger_edit(1)
    assert sig.args == [1]

    # Clear queue hides widget
    w.set_queued_messages([])
    assert not w.isVisible()
    assert w.count() == 0


def test_subagent_running_banner_multiple_and_empty(qtbot):
    b = SubagentRunningBanner()
    qtbot.addWidget(b)

    b.set_running_subagents([
        ("sub1", "Task 1 Reviewer"),
        ("sub2", "Task 2 Implementer"),
    ])
    assert b.isVisible()
    assert b.count() == 2
    banner_text = b.text()
    assert "Task 1 Reviewer" in banner_text
    assert "Task 2 Implementer" in banner_text

    # Setting empty hides banner
    b.set_running_subagents([])
    assert not b.isVisible()
    assert b.count() == 0


def test_agent_input_card_methods_and_shortcuts(qtbot):
    card = AgentInputCard()
    qtbot.addWidget(card)

    # Initial state: send button disabled when input is empty
    assert not card.btn_send.isEnabled()

    card.set_prompt_text("Test query")
    assert card.get_prompt_text() == "Test query"
    assert card.btn_send.isEnabled()

    # Test submission via Enter key
    with qtbot.waitSignal(card.submit_requested, timeout=1000) as sig:
        event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        card.text_edit.keyPressEvent(event)
    prompt, payload = sig.args
    assert prompt == "Test query"
    assert "model" in payload

    # Test clear resets text and disables send button
    card.set_prompt_text("Another query")
    assert card.btn_send.isEnabled()
    card.clear()
    assert card.get_prompt_text() == ""
    assert not card.btn_send.isEnabled()


def test_agent_prompt_dock_queue_action_forwarding(qtbot):
    dock = AgentPromptDock()
    qtbot.addWidget(dock)
    dock.show()

    dock.set_queued_messages(["Queued item"])
    assert dock.queued_widget.isVisible()

    with qtbot.waitSignal(dock.queue_action, timeout=1000) as sig:
        dock.queued_widget.trigger_delete(0)
    action_type, index = sig.args
    assert action_type == "delete"
    assert index == 0

    with qtbot.waitSignal(dock.queue_action, timeout=1000) as sig:
        dock.queued_widget.trigger_send_now(0)
    action_type, index = sig.args
    assert action_type == "send_now"
    assert index == 0
