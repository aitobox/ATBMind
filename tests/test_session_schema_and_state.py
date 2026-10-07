"""
Tests for SessionRecord schema extensions and UIStateManager queue/pinning features.
"""

from apps.atbmind_desktop.state import UIStateManager
from atbmind_core.storage.schemas import SessionRecord


def test_session_record_workspace_and_pinned():
    session = SessionRecord(session_id="s1", title="Test")
    assert session.workspace_name == "ATBMind"
    assert session.is_pinned is False

    session_pinned = SessionRecord(
        session_id="s2", title="Pinned", workspace_name="RepoA", is_pinned=True
    )
    assert session_pinned.workspace_name == "RepoA"
    assert session_pinned.is_pinned is True


def test_ui_state_manager_queued_prompts(qtbot):
    state = UIStateManager()
    session = SessionRecord(session_id="s1", title="Test")
    state.cache_session(session)

    # Pin toggle
    is_pinned = state.toggle_session_pinned("s1")
    assert is_pinned is True
    assert state.get_cached_session("s1").is_pinned is True

    # Prompt queuing
    with qtbot.waitSignal(state.queued_prompts_changed, timeout=1000) as blocker:
        state.queue_prompt("s1", "prompt 1")
    assert blocker.args == ["s1", ["prompt 1"]]
    assert state.get_queued_prompts("s1") == ["prompt 1"]

    state.queue_prompt("s1", "prompt 2")
    assert state.get_queued_prompts("s1") == ["prompt 1", "prompt 2"]

    popped = state.pop_queued_prompt("s1")
    assert popped == "prompt 1"
    assert state.get_queued_prompts("s1") == ["prompt 2"]

    state.remove_queued_prompt("s1", 0)
    assert state.get_queued_prompts("s1") == []


def test_ui_state_manager_queue_edge_cases(qtbot):
    state = UIStateManager()
    session = SessionRecord(session_id="s1", title="Test")
    state.cache_session(session)

    # Unpin toggle
    state.toggle_session_pinned("s1")  # True
    unpinned = state.toggle_session_pinned("s1")  # False
    assert unpinned is False
    assert state.get_cached_session("s1").is_pinned is False

    # Non-existent session pin toggle
    assert state.toggle_session_pinned("non_existent") is False

    # Pop empty queue
    assert state.pop_queued_prompt("s1") is None
    assert state.get_queued_prompts("non_existent") == []

    # Remove out of bounds
    assert state.remove_queued_prompt("s1", 5) is False
    assert state.remove_queued_prompt("s1", -1) is False
