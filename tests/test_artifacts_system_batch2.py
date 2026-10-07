import asyncio
import os
import tempfile
from pathlib import Path
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from atbmind_core.runtime.artifacts import (
    ArtifactManager,
    ArtifactRecord,
    get_global_artifact_manager,
    set_global_artifact_manager,
)
from atbmind_core.runtime.event_bus import (
    AsyncEventBus,
    ArtifactCreatedEvent,
    ArtifactUpdatedEvent,
)
from atbmind_core.runtime.tools.fs_tools import WriteToFileTool
from apps.atbmind_desktop.bridge import EventBusQtBridge
from apps.atbmind_desktop.widgets.inspector_panel import InspectorPanel
from apps.atbmind_desktop.widgets.artifact_viewer import ArtifactViewerDialog
from apps.atbmind_desktop.main_window import ATBMindMainWindow


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.mark.asyncio
async def test_artifact_manager_lifecycle(temp_dir):
    bus = AsyncEventBus()
    received_events = []

    async def on_event(ev):
        received_events.append(ev)

    bus.subscribe(ArtifactCreatedEvent, on_event)
    bus.subscribe(ArtifactUpdatedEvent, on_event)

    mgr = ArtifactManager(storage_dir=temp_dir, event_bus=bus)

    # 1. Create artifact v1
    doc_path = str(temp_dir / "plan.md")
    art1 = mgr.record_artifact(
        file_path=doc_path,
        content="# Plan v1\nStep 1",
        session_id="test_session",
        title="Implementation Plan",
        summary="Detailed plan for rollout",
        request_feedback=True,
    )
    assert art1.version == 1
    assert art1.title == "Implementation Plan"
    assert art1.request_feedback is True
    assert art1.diff == ""

    # Check manifest file
    manifest_file = temp_dir / "test_session" / "manifest.json"
    assert manifest_file.exists()
    snapshot_v1 = temp_dir / "test_session" / f"{art1.artifact_id}_v1.md"
    assert snapshot_v1.exists()
    assert snapshot_v1.read_text(encoding="utf-8") == "# Plan v1\nStep 1"

    await asyncio.sleep(0.01)
    assert len(received_events) == 1
    assert isinstance(received_events[0], ArtifactCreatedEvent)
    assert received_events[0].artifact["artifact_id"] == art1.artifact_id

    # 2. Update artifact to v2
    art2 = mgr.record_artifact(
        file_path=doc_path,
        content="# Plan v2\nStep 1\nStep 2",
        session_id="test_session",
        title="Implementation Plan Updated",
        summary="Updated rollout steps",
        request_feedback=True,
    )
    assert art2.artifact_id == art1.artifact_id
    assert art2.version == 2
    assert "--- v1" in art2.diff
    assert "+++ v2" in art2.diff
    assert "+Step 2" in art2.diff

    snapshot_v2 = temp_dir / "test_session" / f"{art2.artifact_id}_v2.md"
    assert snapshot_v2.exists()

    await asyncio.sleep(0.01)
    assert len(received_events) == 2
    assert isinstance(received_events[1], ArtifactUpdatedEvent)

    # 3. Retrieve
    found = mgr.get_artifact(art1.artifact_id)
    assert found is not None
    assert found.version == 2

    by_path = mgr.get_by_file_path(doc_path)
    assert by_path is not None
    assert by_path.artifact_id == art1.artifact_id

    listed = mgr.list_artifacts(session_id="test_session")
    assert len(listed) == 1


def test_write_to_file_tool_registers_artifact(temp_dir):
    art_dir = temp_dir / "artifacts"
    mgr = ArtifactManager(storage_dir=art_dir)
    set_global_artifact_manager(mgr)

    target_file = str(temp_dir / "my_plan.md")
    tool = WriteToFileTool()
    res = tool.execute(
        TargetFile=target_file,
        CodeContent="# My Project Plan\nEverything works.",
        Overwrite=True,
        Description="Save project plan",
        ArtifactMetadata={
            "Title": "Project Plan",
            "Summary": "Initial system plan",
            "RequestFeedback": True,
            "UserFacing": True,
        },
    )
    assert not res.is_error
    assert os.path.exists(target_file)

    rec = mgr.get_by_file_path(target_file)
    assert rec is not None
    assert rec.title == "Project Plan"
    assert rec.summary == "Initial system plan"
    assert rec.request_feedback is True

    # Reset
    set_global_artifact_manager(None)


def test_event_bus_qt_bridge_artifact_signals(qapp):
    bridge = EventBusQtBridge()
    created_emitted = []
    updated_emitted = []

    bridge.artifact_created.connect(lambda a: created_emitted.append(a))
    bridge.artifact_updated.connect(lambda a: updated_emitted.append(a))

    bridge.emit_artifact_created({"artifact_id": "art-1", "title": "Test 1"})
    assert len(created_emitted) == 1
    assert created_emitted[0]["artifact_id"] == "art-1"

    bridge.emit_artifact_updated({"artifact_id": "art-1", "title": "Test 1 rev"})
    assert len(updated_emitted) == 1
    assert updated_emitted[0]["title"] == "Test 1 rev"


def test_inspector_and_artifact_viewer_dialog(qtbot, temp_dir):
    inspector = InspectorPanel()
    qtbot.addWidget(inspector)
    sample_art = {
        "artifact_id": "art-101",
        "title": "Architecture Spec",
        "summary": "Spec overview",
        "version": 2,
        "content": "# Architecture Spec\n\nContent goes here.",
        "diff": "--- v1\n+++ v2\n+Added spec details",
        "request_feedback": True,
    }
    inspector.update_artifacts([sample_art])
    assert inspector.section_artifacts.item_count() == 1

    dialog = ArtifactViewerDialog(sample_art, parent=inspector)
    qtbot.addWidget(dialog)
    assert dialog.title_label.text() == "Architecture Spec"
    assert dialog.badge_ver.text() == "v2"
    assert dialog.btn_proceed is not None
    assert dialog.btn_revise is not None

    proceed_received = []
    dialog.proceed_requested.connect(lambda aid: proceed_received.append(aid))
    dialog._on_proceed_clicked()
    assert proceed_received == ["art-101"]

    revise_received = []
    dialog.revise_requested.connect(lambda aid, fb: revise_received.append((aid, fb)))
    dialog.input_feedback.setText("Please expand section 3")
    dialog._on_revise_clicked()
    assert revise_received == [("art-101", "Please expand section 3")]


def test_main_window_artifact_integration(qtbot, temp_dir, monkeypatch):
    from atbmind_core.config import AppConfig, StorageConfig
    cfg = AppConfig(storage=StorageConfig(db_path=str(temp_dir / "test.db")))
    win = ATBMindMainWindow(config=cfg)
    qtbot.addWidget(win)

    art = {
        "artifact_id": "art-999",
        "title": "Release Plan",
        "version": 1,
        "content": "# Release v1.0",
        "summary": "Checklist",
        "request_feedback": True,
    }

    # Emit artifact created through event_bridge
    win.event_bridge.emit_artifact_created(art)
    assert "art-999" in win._artifacts_map
    assert win.inspector.section_artifacts.item_count() == 1

    # Test Proceed action triggers handle_submit_request
    prompts_sent = []
    monkeypatch.setattr(win, "handle_submit_request", lambda p, a, s: prompts_sent.append(p))

    win._on_artifact_proceed("art-999")
    assert len(prompts_sent) == 1
    assert "Proceed with execution of plan: Release Plan" in prompts_sent[0]

    # Test Revise action triggers handle_submit_request
    win._on_artifact_revise("art-999", "Need more test cases")
    assert len(prompts_sent) == 2
    assert "Need more test cases" in prompts_sent[1]

    win.close()
