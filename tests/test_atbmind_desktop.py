"""
End-to-End Desktop & Async Pipeline Tests for ATBMind (Issue #38).
Verifies GenerationWorker, TitleWorker, single-writer SQLite persistence,
non-blocking multi-session switching, and multi-turn refinement loop.
"""

from __future__ import annotations

from pathlib import Path
import time
import pytest
from PySide6.QtCore import Qt

from atbmind_core.config import AppConfig
from atbmind_core.storage.session_store import SessionStore
from apps.atbmind_desktop.main_window import ATBMindMainWindow
from apps.atbmind_desktop.widgets.chat_stream import (
    AssistantTextMessageItem,
    DrawResultCardItem,
    ErrorResultCard,
)
from apps.atbmind_desktop.workers import GenerationWorker, TitleWorker


class DummyLLMClient:
    """Deterministic stub LLM client for testing worker pipelines."""

    def __init__(self, reply_text: str = "这是助手的回复内容", should_fail: bool = False) -> None:
        self.reply_text = reply_text
        self.should_fail = should_fail
        self.calls = []

    def chat_completion(self, messages, **kwargs) -> str:
        self.calls.append(messages)
        if self.should_fail:
            raise RuntimeError("模拟 LLM 网络超时错误")
        return self.reply_text

    def generate_structured_json(self, messages, schema=None, **kwargs):
        self.calls.append(messages)
        if self.should_fail:
            raise RuntimeError("模拟结构化解析失败")
        if schema is not None:
            return schema(
                request_id="req-test-001",
                plugin_id="draw",
                intent_category="skin_lighting",
                target_entities=[{"entity_id": "person_1", "label": "face"}],
                parameters={"smooth_strength": 0.5, "preserve_skin_texture": True},
            )
        return {"selected_templates": ["T_DRAW_SKIN_TEXTURE"]}


@pytest.fixture
def desktop_store(tmp_path):
    db_file = tmp_path / "test_atbmind.db"
    gen_dir = tmp_path / "generated_images"
    return SessionStore(
        db_path=str(db_file),
        generated_images_dir=str(gen_dir),
    )


def test_generation_worker_draw_pipeline(qtbot, tmp_path):
    """GenerationWorker executes Layer 1 -> Layer 2 -> Layer 3 and saves output image."""
    before_img = tmp_path / "input_portrait.png"
    before_img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
    gen_dir = tmp_path / "generated_images"

    llm_stub = DummyLLMClient()
    worker = GenerationWorker(
        session_id="sess-draw-01",
        prompt="帮我把皮肤做双频磨皮，自然通透",
        attachment_path=str(before_img),
        active_plugin_id="draw",
        plugin_state={
            "model": "Mock Adapter",
            "aspect_ratio": "1:1",
            "style_id": "portrait",
            "template_id": "双频原生磨皮",
        },
        generated_images_dir=str(gen_dir),
        llm_client=llm_stub,
    )

    progress_events = []
    finished_events = []
    worker.progress_updated.connect(lambda sid, msg: progress_events.append((sid, msg)))
    worker.finished.connect(lambda sid, rep, path: finished_events.append((sid, rep, path)))

    with qtbot.waitSignal(worker.finished, timeout=5000):
        worker.start()

    worker.wait(2000)

    assert len(progress_events) >= 2
    assert all(sid == "sess-draw-01" for sid, _ in progress_events)
    assert len(finished_events) == 1
    sid, report, image_path = finished_events[0]
    assert sid == "sess-draw-01"
    assert report.success is True
    assert Path(image_path).is_file()
    assert Path(image_path).parent == gen_dir
    assert Path(image_path).stat().st_size > 0


def test_generation_worker_plain_text_and_failure(qtbot, tmp_path):
    """GenerationWorker emits text_finished in plain-text mode and failed on unhandled error."""
    # 1. Plain-text mode success
    llm_ok = DummyLLMClient(reply_text="您好！我可以帮您处理人像修图或回答问题。")
    w_ok = GenerationWorker(
        session_id="sess-text",
        prompt="你好，请问你能做什么？",
        attachment_path="",
        active_plugin_id=None,
        plugin_state={},
        generated_images_dir=str(tmp_path / "gen"),
        llm_client=llm_ok,
    )
    text_results = []
    w_ok.text_finished.connect(lambda sid, txt: text_results.append((sid, txt)))

    with qtbot.waitSignal(w_ok.text_finished, timeout=5000):
        w_ok.start()
    w_ok.wait(2000)

    assert text_results == [("sess-text", "您好！我可以帮您处理人像修图或回答问题。")]

    # 2. Failure mode
    llm_fail = DummyLLMClient(should_fail=True)
    w_fail = GenerationWorker(
        session_id="sess-err",
        prompt="触发异常测试",
        attachment_path="",
        active_plugin_id=None,
        plugin_state={},
        generated_images_dir=str(tmp_path / "gen"),
        llm_client=llm_fail,
    )
    fail_results = []
    w_fail.failed.connect(lambda sid, err: fail_results.append((sid, err)))

    with qtbot.waitSignal(w_fail.failed, timeout=5000):
        w_fail.start()
    w_fail.wait(2000)

    assert len(fail_results) == 1
    assert fail_results[0][0] == "sess-err"
    assert "模拟 LLM 网络超时错误" in fail_results[0][1]


def test_title_worker_summary(qtbot):
    """TitleWorker generates concise 4-8 word/character conversation summary asynchronously."""
    llm_stub = DummyLLMClient(reply_text="「双频人像磨皮精修」")
    tw = TitleWorker(
        session_id="sess-title-1",
        first_prompt="请帮我把这张照片做一下双频原生磨皮和瘦脸处理",
        llm_client=llm_stub,
    )
    titles = []
    tw.title_generated.connect(lambda sid, t: titles.append((sid, t)))

    with qtbot.waitSignal(tw.title_generated, timeout=5000):
        tw.start()
    tw.wait(2000)

    assert len(titles) == 1
    assert titles[0][0] == "sess-title-1"
    assert titles[0][1] == "双频人像磨皮精修"


def test_end_to_end_first_turn_title_and_draw_generation(qtbot, desktop_store, tmp_path):
    """
    First turn triggers asynchronous TitleWorker (updating sidebar/header)
    and GenerationWorker (persisting MessageRecord and rendering DrawResultCardItem).
    """
    config = AppConfig()
    win = ATBMindMainWindow(session_store=desktop_store, config=config)
    qtbot.addWidget(win)
    win.show()

    sess_id = win.state_manager.active_session_id
    assert sess_id is not None
    assert desktop_store.get_session(sess_id).title == "新对话"

    # Mount ATBDraw plugin & attach image
    input_img = tmp_path / "portrait_raw.png"
    input_img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
    win.footer_dock.load_plugin("draw", {"model": "Mock Adapter", "template_id": "双频原生磨皮"})
    win.footer_dock.set_attachment(str(input_img))
    win.footer_dock.set_prompt_text("请帮我进行面部双频自然磨皮")

    # Click send
    qtbot.mouseClick(win.footer_dock.send_btn, Qt.MouseButton.LeftButton)

    # Wait until both GenerationWorker (2 messages in store) and TitleWorker complete
    def _turn_completed():
        msgs = desktop_store.get_messages(sess_id)
        sess = desktop_store.get_session(sess_id)
        return (
            len(msgs) == 2
            and not win.state_manager.is_in_flight(sess_id)
            and sess is not None
            and sess.title != "新对话"
        )

    qtbot.waitUntil(_turn_completed, timeout=5000)

    # Verify title updated in store, header, and sidebar
    updated_sess = desktop_store.get_session(sess_id)
    assert updated_sess.title != "新对话"
    assert win.chat_stream.header_bar.title_label.text() == updated_sess.title

    # Verify messages persisted via main thread single-writer
    msgs = desktop_store.get_messages(sess_id)
    assert len(msgs) == 2
    assert msgs[0].role == "user"
    assert msgs[1].role == "assistant"
    assert msgs[1].plugin_id == "draw"
    assert msgs[1].plugin_payload is not None
    assert Path(msgs[1].plugin_payload["after_img"]).is_file()

    # Verify DrawResultCardItem rendered in ChatStreamView
    cards = win.chat_stream.findChildren(DrawResultCardItem)
    assert len(cards) == 1
    assert cards[0].after_path == msgs[1].plugin_payload["after_img"]


def test_non_blocking_session_switching_during_generation(qtbot, desktop_store, tmp_path):
    """
    Users can freely switch sessions during generation; sidebar displays spinner on in-flight session,
    and completed cards appear only in the originating session.
    """
    config = AppConfig()
    win = ATBMindMainWindow(session_store=desktop_store, config=config)
    win._worker_delay_ms = 250  # Add controlled delay to observe in-flight state and switch sessions
    qtbot.addWidget(win)
    win.show()

    sess_a = win.state_manager.active_session_id
    input_img = tmp_path / "source_a.png"
    input_img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

    win.footer_dock.load_plugin("draw", {"model": "Mock Adapter", "template_id": "智能全身自然显瘦塑形"})
    win.footer_dock.set_attachment(str(input_img))
    win.footer_dock.set_prompt_text("全身显瘦塑形处理")

    # Trigger submission on Session A
    qtbot.mouseClick(win.footer_dock.send_btn, Qt.MouseButton.LeftButton)

    # Session A must immediately be marked in-flight with sidebar spinner
    assert win.state_manager.is_in_flight(sess_a) is True
    assert win.sidebar._in_flight_states.get(sess_a) is True

    # Immediately create and switch to Session B while Session A is still generating
    sess_b_record = win.create_new_session()
    sess_b = sess_b_record.session_id
    assert win.state_manager.active_session_id == sess_b

    # Wait for Session A's background generation to complete while viewing Session B
    qtbot.waitUntil(lambda: not win.state_manager.is_in_flight(sess_a), timeout=5000)

    # Sidebar spinner for Session A must now be False
    assert win.sidebar._in_flight_states.get(sess_a) is False

    # Session B's chat stream must NOT have Session A's result card
    assert len(win.chat_stream.findChildren(DrawResultCardItem)) == 0
    assert len(desktop_store.get_messages(sess_b)) == 0

    # Session A's messages in store must contain both user and assistant records
    msgs_a = desktop_store.get_messages(sess_a)
    assert len(msgs_a) == 2
    assert msgs_a[1].plugin_payload is not None

    # Switch back to Session A -> completed DrawResultCardItem must now be rendered
    win.switch_session(sess_a)
    cards_a = win.chat_stream.findChildren(DrawResultCardItem)
    assert len(cards_a) == 1
    assert cards_a[0].before_path == str(input_img)


def test_multi_turn_refinement_loop(qtbot, desktop_store, tmp_path):
    """
    Clicking '[↺ 以此结果微调]' on DrawResultCard populates FooterDock AttachmentChip
    with the generated image and prefills '在此基础上：', feeding it into the next turn.
    """
    config = AppConfig()
    win = ATBMindMainWindow(session_store=desktop_store, config=config)
    qtbot.addWidget(win)
    win.show()

    sess_id = win.state_manager.active_session_id
    raw_img = tmp_path / "turn1_input.png"
    raw_img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

    win.footer_dock.load_plugin("draw", {"model": "Mock Adapter", "template_id": "双频原生磨皮"})
    win.footer_dock.set_attachment(str(raw_img))
    win.footer_dock.set_prompt_text("第一轮：基础自然磨皮")
    qtbot.mouseClick(win.footer_dock.send_btn, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: len(desktop_store.get_messages(sess_id)) == 2, timeout=5000)

    cards = win.chat_stream.findChildren(DrawResultCardItem)
    assert len(cards) == 1
    turn1_after_img = cards[0].after_path
    assert Path(turn1_after_img).is_file()

    # Click '[↺ 以此结果微调]' button on the card
    refine_btn = cards[0].findChild(type(win.footer_dock.send_btn), "refineBtn")
    assert refine_btn is not None
    qtbot.mouseClick(refine_btn, Qt.MouseButton.LeftButton)

    # Verify FooterDock populated with turn1_after_img and '在此基础上：'
    assert win.footer_dock.attachment_path == turn1_after_img
    assert win.footer_dock.chip_container.isVisible()
    assert win.footer_dock.text_edit.toPlainText() == "在此基础上："

    # Complete prompt for Turn 2 and submit
    win.footer_dock.set_prompt_text("在此基础上：进一步加强下颌线立体轮廓")
    qtbot.mouseClick(win.footer_dock.send_btn, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: len(desktop_store.get_messages(sess_id)) == 4, timeout=5000)

    msgs = desktop_store.get_messages(sess_id)
    assert len(msgs) == 4
    # Turn 2 user message attachment must be Turn 1's output image
    assert msgs[2].role == "user"
    assert msgs[2].attachment_path == turn1_after_img
    # Turn 2 assistant card before_img must be Turn 1's output image
    assert msgs[3].role == "assistant"
    assert msgs[3].plugin_payload["before_img"] == turn1_after_img
    assert Path(msgs[3].plugin_payload["after_img"]).is_file()
    assert msgs[3].plugin_payload["after_img"] != turn1_after_img
