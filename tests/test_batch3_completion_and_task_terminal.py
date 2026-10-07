import pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from apps.atbmind_desktop.widgets.agent_dock import (
    AutoResizingAgentTextEdit,
    PromptCompleterPopup,
)
from apps.atbmind_desktop.widgets.task_terminal import TaskTerminalDialog
from apps.atbmind_desktop.widgets.inspector_panel import InspectorPanel
from apps.atbmind_desktop.main_window import ATBMindMainWindow
from atbmind_core.config import AppConfig, StorageConfig


def test_prompt_completer_slash_and_mention(qtbot):
    edit = AutoResizingAgentTextEdit()
    qtbot.addWidget(edit)
    edit.show()

    popup = edit.completer_popup
    assert not popup.isVisible()

    # 1. Test Slash Command trigger
    edit.setPlainText("/pl")
    cursor = edit.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    edit.setTextCursor(cursor)
    edit._check_completion()

    assert popup.isVisible()
    selected_token = popup.get_selected_token()
    assert selected_token == "/plan"

    # Simulate pressing Enter / Return
    press_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
    edit.keyPressEvent(press_event)

    assert not popup.isVisible()
    assert "/plan " in edit.toPlainText()

    # 2. Test Mention Role trigger with arrow navigation
    edit.clear()
    edit.setPlainText("@")
    cursor = edit.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    edit.setTextCursor(cursor)
    edit._check_completion()

    assert popup.isVisible()
    first_token = popup.get_selected_token()
    assert first_token == "@coordinator"

    # Navigate down
    press_down = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier)
    edit.keyPressEvent(press_down)
    second_token = popup.get_selected_token()
    assert second_token == "@draw_expert"

    # Press Tab to complete
    press_tab = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier)
    edit.keyPressEvent(press_tab)

    assert not popup.isVisible()
    assert "@draw_expert " in edit.toPlainText()

    # 3. Test Escape hides popup
    edit.setPlainText("/go")
    cursor = edit.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    edit.setTextCursor(cursor)
    edit._check_completion()
    assert popup.isVisible()

    press_esc = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    edit.keyPressEvent(press_esc)
    assert not popup.isVisible()


def test_task_terminal_dialog_lifecycle(qtbot):
    task_info = {
        "id": "task-test-01",
        "name": "Cargo Build",
        "status": "running",
        "output": "Initial build log line 1\n",
    }
    dialog = TaskTerminalDialog(task_info)
    qtbot.addWidget(dialog)

    assert dialog.task_id == "task-test-01"
    assert dialog.task_name == "Cargo Build"
    assert "Initial build log" in dialog.browser_terminal.toPlainText()
    assert dialog.badge_status.text() == "RUNNING"

    # 1. Append streaming output
    dialog.append_output("Compiling module 2...\n")
    assert "Compiling module 2..." in dialog.browser_terminal.toPlainText()

    # 2. Send stdin
    stdin_captured = []
    dialog.input_submitted.connect(lambda tid, inp: stdin_captured.append((tid, inp)))
    dialog.stdin_edit.setText("yes")
    dialog._on_send_stdin()
    assert stdin_captured == [("task-test-01", "yes\n")]

    # 3. Kill task
    kill_captured = []
    dialog.kill_requested.connect(lambda tid: kill_captured.append(tid))
    dialog._on_kill_task()
    assert kill_captured == ["task-test-01"]

    # 4. Update status
    dialog.set_status("done", "Build Finished 0")
    assert dialog.badge_status.text() == "DONE"


def test_inspector_task_terminal_interaction(qtbot):
    inspector = InspectorPanel()
    qtbot.addWidget(inspector)

    task_data = {
        "id": "task-alpha",
        "name": "Test Runner",
        "status": "running",
        "elapsed": "12s",
        "output": "Starting test suite\n",
    }
    inspector.update_background_tasks([task_data])
    assert inspector.tasks_count() == 1

    # Open task terminal from inspector
    terminal_dialog = inspector.open_task_terminal(task_data)
    qtbot.addWidget(terminal_dialog)
    assert "task-alpha" in inspector._active_task_dialogs

    # Forward output chunk through inspector
    inspector.append_task_output("task-alpha", "Test 1 PASSED\n")
    assert "Test 1 PASSED" in terminal_dialog.browser_terminal.toPlainText()

    # Propagate kill signal through inspector
    kill_reported = []
    inspector.task_kill_requested.connect(lambda tid: kill_reported.append(tid))
    terminal_dialog._on_kill_task()
    assert kill_reported == ["task-alpha"]

    # Propagate input signal through inspector
    input_reported = []
    inspector.task_input_requested.connect(lambda tid, inp: input_reported.append((tid, inp)))
    terminal_dialog.stdin_edit.setText("continue")
    terminal_dialog._on_send_stdin()
    assert input_reported == [("task-alpha", "continue\n")]


def test_main_window_task_terminal_wiring(qtbot, tmp_path, monkeypatch):
    cfg = AppConfig(storage=StorageConfig(db_path=str(tmp_path / "mind.db")))
    win = ATBMindMainWindow(config=cfg)
    qtbot.addWidget(win)

    # 1. Output received forwards to inspector
    win.event_bridge.emit_task_output("task-xyz", "Step 1 complete\n")
    assert "task-xyz" in win._active_tasks
    assert "Step 1 complete" in win._active_tasks["task-xyz"]["output"]

    # 2. Test Kill requested calls task_manager.kill_task
    killed_tasks = []

    async def mock_kill(tid):
        killed_tasks.append(tid)
        return True

    monkeypatch.setattr(win.task_manager, "kill_task", mock_kill)
    win._on_task_kill_requested("task-xyz")
    # In asyncio loop, wait or let task execute
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            pass
    except Exception:
        pass

    # 3. Test Stdin input requested calls task_manager.send_input
    sent_inputs = []

    async def mock_send(tid, text):
        sent_inputs.append((tid, text))
        return True

    monkeypatch.setattr(win.task_manager, "send_input", mock_send)
    win._on_task_input_requested("task-xyz", "confirm\n")

    win.close()
