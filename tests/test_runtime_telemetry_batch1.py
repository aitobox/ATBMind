import asyncio
import os
import tempfile
import pytest
from PySide6.QtCore import Qt

from atbmind_core.runtime.event_bus import (
    AsyncEventBus,
    FilesChangedEvent,
    SubagentLifecycleEvent,
    TaskOutputEvent,
    TaskStatusChangedEvent,
    get_global_event_bus,
    set_global_event_bus,
)
from atbmind_core.runtime.tools.fs_tools import (
    WriteToFileTool,
    ReplaceFileContentTool,
)
from apps.atbmind_desktop.main_window import ATBMindMainWindow
from atbmind_core.storage.session_store import SessionStore
from atbmind_core.config import AppConfig


@pytest.mark.asyncio
async def test_fs_tools_emit_files_changed_event(tmp_path):
    bus = AsyncEventBus()
    received_events = []

    async def _on_files(event: FilesChangedEvent):
        received_events.append(event)

    bus.subscribe(FilesChangedEvent, _on_files)

    target_file = tmp_path / "hello.txt"
    writer = WriteToFileTool(event_bus=bus)

    # 1. New file creation
    res = await writer.execute_async({
        "TargetFile": str(target_file),
        "CodeContent": "line 1\nline 2\nline 3\n",
    })
    assert not res.is_error
    assert len(received_events) == 1
    ev1 = received_events[0]
    assert len(ev1.files) == 1
    assert ev1.files[0]["status"] == "added"
    assert ev1.files[0]["insertions"] == 3
    assert ev1.files[0]["deletions"] == 0

    # 2. File replacement
    replacer = ReplaceFileContentTool(event_bus=bus)
    res2 = await replacer.execute_async({
        "TargetFile": str(target_file),
        "StartLine": 2,
        "EndLine": 2,
        "TargetContent": "line 2",
        "ReplacementContent": "line 2 modified\nline 2.5 added",
    })
    assert not res2.is_error
    assert len(received_events) == 2
    ev2 = received_events[1]
    assert ev2.files[0]["status"] == "modified"
    assert ev2.files[0]["insertions"] == 2
    assert ev2.files[0]["deletions"] == 1


def test_main_window_runtime_wiring_and_telemetry(qtbot, tmp_path):
    db_file = tmp_path / "test_mind.db"
    store = SessionStore(db_path=str(db_file))
    cfg = AppConfig()

    bus = AsyncEventBus()
    set_global_event_bus(bus)

    win = ATBMindMainWindow(session_store=store, config=cfg)
    qtbot.addWidget(win)

    # Verify event_bus, task_manager, orchestrator, and event_bridge are attached
    assert win.event_bus is not None
    assert win.task_manager is not None
    assert win.orchestrator is not None
    assert win.event_bridge.bus is win.event_bus

    # 1. Test FilesChangedEvent updates inspector
    file_info = {"path": "src/core.py", "status": "modified", "insertions": 10, "deletions": 2}
    win.event_bridge.emit_files_changed([file_info])
    assert win.inspector.files_count() == 1

    # 2. Test TaskOutputEvent & TaskStatus updates inspector
    win.event_bridge.emit_task_output("task-100", "Building step 1...\n")
    assert "task-100" in win._active_tasks
    assert "Building step 1" in win._active_tasks["task-100"]["output"]

    win.event_bridge.emit_task_status("task-100", "done", "Build success")
    assert win.inspector.tasks_count() >= 1

    # 3. Test SubagentLifecycleEvent updates inspector and banner
    win.event_bridge.emit_subagent_lifecycle("sub-99", "running", "Analyzing repo")
    assert win.inspector.subagent_count() == 1
    assert win.work_stream.prompt_dock.running_banner.count() == 1

    # 4. Test StepElapsedPill creation via _on_worker_step_done
    active_id = win.state_manager.active_session_id
    win._on_worker_step_done(active_id, "正在执行工具: run_command...")
    # Chat stream should have added a step elapsed pill
    widgets = [win.chat_stream.messages_layout.itemAt(i).widget() for i in range(win.chat_stream.messages_layout.count())]
    has_pill = any(type(w).__name__ == "StepElapsedPill" for w in widgets if w)
    assert has_pill

    win.close()
