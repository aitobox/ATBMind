"""
Tests for ATBMindMainWindow Assembly & UI State Coordinator (Issue #37).
Validates signal connections, multi-session persistence coordination,
and widget integration adhering to Apple HIG specs.
"""

from __future__ import annotations

from pathlib import Path
import time
import uuid
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from atbmind_core.config import AppConfig
from atbmind_core.plugins.schemas import MessageRecord, SessionRecord
from atbmind_core.storage.session_store import SessionStore
from apps.atbmind_desktop.main import create_app
from apps.atbmind_desktop.main_window import ATBMindMainWindow
from apps.atbmind_desktop.state import UIStateManager
from apps.atbmind_desktop.widgets.chat_stream import ChatStreamView
from apps.atbmind_desktop.widgets.footer_dock import FooterDock
from apps.atbmind_desktop.widgets.image_viewer import ImageViewerDialog
from apps.atbmind_desktop.widgets.settings_dialog import SettingsDialog
from apps.atbmind_desktop.widgets.sidebar import SidebarWidget


@pytest.fixture
def in_memory_store(tmp_path):
    return SessionStore(
        db_path=":memory:",
        generated_images_dir=str(tmp_path / "gen_imgs"),
    )


def test_ui_state_manager(qtbot):
    manager = UIStateManager()
    active_emitted = []
    in_flight_emitted = []
    plugin_emitted = []

    manager.active_session_changed.connect(active_emitted.append)
    manager.session_in_flight_changed.connect(lambda s, f: in_flight_emitted.append((s, f)))
    manager.plugin_state_changed.connect(lambda s, p, d: plugin_emitted.append((s, p, d)))

    record = SessionRecord(
        session_id="s1",
        title="Test Session",
        active_plugin_id=None,
        plugin_state={},
        created_at=time.time(),
        updated_at=time.time(),
    )
    manager.cache_session(record)
    assert manager.get_cached_session("s1") == record

    manager.set_active_session("s1")
    assert manager.active_session_id == "s1"
    assert active_emitted == ["s1"]
    assert manager.get_active_session() == record

    # In flight
    assert not manager.is_in_flight("s1")
    manager.set_in_flight("s1", True)
    assert manager.is_in_flight("s1")
    assert in_flight_emitted == [("s1", True)]
    manager.set_in_flight("s1", False)
    assert not manager.is_in_flight("s1")
    assert in_flight_emitted == [("s1", True), ("s1", False)]

    # Plugin state
    manager.update_plugin_state("s1", "draw", {"model": "Flux.1"})
    assert record.active_plugin_id == "draw"
    assert record.plugin_state == {"model": "Flux.1"}
    assert plugin_emitted == [("s1", "draw", {"model": "Flux.1"})]

    # Remove
    manager.remove_cached_session("s1")
    assert manager.active_session_id is None
    assert manager.get_cached_session("s1") is None


def test_sidebar_widget(qtbot):
    sidebar = SidebarWidget()
    qtbot.addWidget(sidebar)
    sidebar.show()

    new_emitted = []
    selected_emitted = []
    settings_emitted = []

    sidebar.new_session_requested.connect(lambda: new_emitted.append(True))
    sidebar.session_selected.connect(selected_emitted.append)
    sidebar.open_settings_requested.connect(lambda: settings_emitted.append(True))

    s1 = SessionRecord(
        session_id="sess-1",
        title="Session One",
        active_plugin_id="draw",
        plugin_state={},
        created_at=time.time(),
        updated_at=time.time(),
    )
    s2 = SessionRecord(
        session_id="sess-2",
        title="Session Two",
        active_plugin_id=None,
        plugin_state={},
        created_at=time.time(),
        updated_at=time.time(),
    )

    sidebar.set_sessions([s1, s2], active_session_id="sess-1")
    assert sidebar.list_widget.count() == 2

    # Click + 新对话
    qtbot.mouseClick(sidebar.new_btn, Qt.MouseButton.LeftButton)
    assert len(new_emitted) == 1

    # Click settings
    qtbot.mouseClick(sidebar.settings_btn, Qt.MouseButton.LeftButton)
    assert len(settings_emitted) == 1

    # Select session item
    item = sidebar._session_items["sess-2"]
    sidebar.list_widget.itemClicked.emit(item)
    assert selected_emitted == ["sess-2"]

    # In flight status
    sidebar.set_in_flight("sess-1", True)
    assert sidebar._in_flight_states["sess-1"] is True

    # Remove session
    sidebar.remove_session("sess-2")
    assert sidebar.list_widget.count() == 1


def test_chat_stream_view(qtbot, tmp_path):
    view = ChatStreamView()
    qtbot.addWidget(view)
    view.show()

    view.set_session_info("人像精修会话", "draw")
    assert "ATBDraw" in view.header_bar.badge_label.text()

    # User message
    img_file = tmp_path / "test.png"
    img_file.write_bytes(b"dummy")
    view.add_user_message("帮我把脸部磨皮", attachment_path=str(img_file))
    assert view.messages_layout.count() >= 2  # message + stretch

    # Assistant message
    view.add_assistant_message("正在为您精修...")
    assert view.messages_layout.count() >= 3

    # Plugin Result Card
    view.add_plugin_result({
        "before_img": str(img_file),
        "after_img": str(img_file),
        "elapsed_seconds": 1.5,
        "template_name": "双频原生磨皮",
    })
    assert view.messages_layout.count() >= 4

    # Error Card
    view.add_error_card("模型网络连接超时")
    assert view.messages_layout.count() >= 5

    # Clear
    view.clear_messages()
    assert view.messages_layout.count() == 1  # Only bottom stretch remaining


def test_footer_dock(qtbot, tmp_path):
    dock = FooterDock()
    qtbot.addWidget(dock)
    dock.show()

    # Initial state: plain-text mode
    assert dock.load_plugin_btn.isVisible()
    assert not dock.capsule_btn.isVisible()
    assert dock.get_plugin_state() == {}

    # Load plugin
    dock.load_plugin("draw", {"model": "Flux.1", "aspect_ratio": "16:9", "style_id": "anime"})
    assert not dock.load_plugin_btn.isVisible()
    assert dock.capsule_btn.isVisible()
    state = dock.get_plugin_state()
    assert state["model"] == "Flux.1"
    assert state["aspect_ratio"] == "16:9"
    assert state["style_id"] == "anime"

    # Attachment
    img_path = str(tmp_path / "avatar.jpg")
    Path(img_path).write_bytes(b"dummy")
    dock.set_attachment(img_path)
    assert dock.attachment_path == img_path
    assert dock.chip_container.isVisible()

    # Submit
    submitted = []
    dock.submit_requested.connect(lambda p, a, s: submitted.append((p, a, s)))
    dock.set_prompt_text("全身自然显瘦")
    qtbot.mouseClick(dock.send_btn, Qt.MouseButton.LeftButton)

    assert len(submitted) == 1
    prompt, att, p_state = submitted[0]
    assert prompt == "全身自然显瘦"
    assert att == img_path
    assert p_state["model"] == "Flux.1"

    # Unload plugin
    dock.unload_plugin()
    assert dock.load_plugin_btn.isVisible()
    assert not dock.capsule_btn.isVisible()


def test_settings_dialog(qtbot, tmp_path, monkeypatch):
    from atbmind_core.engine.llm_client import OpenAICompatClient
    monkeypatch.setattr(OpenAICompatClient, "chat_completion", lambda self, messages, **kwargs: "pong")

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("""
app_name: ATBMind
llm:
  provider: openai
  base_url: https://api.openai.com/v1
  api_key: sk-initial
  model: gpt-4o
  temperature: 0.2
""", encoding="utf-8")

    from atbmind_core.config import load_config
    cfg = load_config(cfg_file)

    dlg = SettingsDialog(config=cfg)
    qtbot.addWidget(dlg)

    assert dlg.base_url_edit.text() == "https://api.openai.com/v1"
    assert dlg.api_key_edit.text() == "sk-initial"

    # Reveal toggle
    assert dlg.api_key_edit.echoMode() == dlg.api_key_edit.EchoMode.Password
    dlg.reveal_cb.setChecked(True)
    assert dlg.api_key_edit.echoMode() == dlg.api_key_edit.EchoMode.Normal

    # Test connection
    dlg._on_test_connection()
    assert "有效" in dlg.status_label.text()


def test_image_viewer_dialog(qtbot, tmp_path):
    img = tmp_path / "test.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR...")
    dlg = ImageViewerDialog(str(img))
    qtbot.addWidget(dlg)
    dlg.show()
    assert dlg.windowTitle() == f"预览: {img.name}"


def test_main_window_assembly(qtbot, in_memory_store):
    config = AppConfig()
    win = ATBMindMainWindow(session_store=in_memory_store, config=config)
    qtbot.addWidget(win)
    win.show()

    # Initial session auto-created
    assert win.state_manager.active_session_id is not None
    init_sess_id = win.state_manager.active_session_id
    assert win.sidebar.list_widget.count() == 1

    # Create new session
    new_sess = win.create_new_session()
    assert win.state_manager.active_session_id == new_sess.session_id
    assert win.sidebar.list_widget.count() == 2

    # Switch back to initial session
    win.switch_session(init_sess_id)
    assert win.state_manager.active_session_id == init_sess_id

    # Mount plugin on active session
    win.footer_dock.load_plugin("draw", {"model": "Flux.1", "aspect_ratio": "1:1"})
    sess_rec = in_memory_store.get_session(init_sess_id)
    assert sess_rec.active_plugin_id == "draw"
    assert sess_rec.plugin_state["model"] == "Flux.1"

    # Submit message
    win.footer_dock.set_prompt_text("请生成复古人像写真")
    qtbot.mouseClick(win.footer_dock.send_btn, Qt.MouseButton.LeftButton)

    msgs = in_memory_store.get_messages(init_sess_id)
    assert len(msgs) == 1
    assert msgs[0].content == "请生成复古人像写真"
    assert msgs[0].role == "user"

    # Rename session
    win.rename_session(init_sess_id, "复古写真设计")
    assert in_memory_store.get_session(init_sess_id).title == "复古写真设计"
    assert win.chat_stream.header_bar.title_label.text() == "复古写真设计"

    # Refine request
    win.handle_refine_request("/tmp/after.png", "在此基础上：")
    assert win.footer_dock.attachment_path == "/tmp/after.png"
    assert win.footer_dock.text_edit.toPlainText() == "在此基础上："

    # Clear current history
    win.clear_current_history()
    assert len(in_memory_store.get_messages(init_sess_id)) == 0

    # Delete session
    win.delete_session(new_sess.session_id)
    assert in_memory_store.get_session(new_sess.session_id) is None
    assert win.sidebar.list_widget.count() == 1


def test_main_create_app():
    app = create_app(["--test"])
    assert isinstance(app, QApplication)
    assert app.applicationName() == "ATBMind"
