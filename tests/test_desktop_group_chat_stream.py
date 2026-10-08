"""Unit tests for ChatStreamView multi-expert concurrent stream demuxing and speaker badges (Issue #78)."""

import pytest

from apps.atbmind_desktop.widgets.chat_stream import ChatStreamView
from apps.atbmind_desktop.widgets.message_bubble import AssistantTextMessageItem


def test_concurrent_multi_expert_stream_demuxing(qtbot):
    chat = ChatStreamView()
    qtbot.addWidget(chat)
    chat.show()

    assert chat.message_count() == 0
    assert len(chat._active_bubbles) == 0

    # 1. Coder starts streaming
    b_coder = chat.append_speaker_delta(
        speaker_role_id="coder",
        speaker_name="代码专家",
        delta="def calculate():\n",
        speaker_avatar="💻",
        is_start=True,
    )
    assert chat.message_count() == 1
    assert "coder" in chat._active_bubbles
    assert chat._active_bubbles["coder"] is b_coder

    # 2. Draw expert starts streaming concurrently (interleaved)
    b_draw = chat.append_speaker_delta(
        speaker_role_id="draw_expert",
        speaker_name="绘图专家",
        delta="开始绘制线稿...\n",
        speaker_avatar="🎨",
        is_start=True,
    )
    assert chat.message_count() == 2
    assert "draw_expert" in chat._active_bubbles
    assert chat._active_bubbles["draw_expert"] is b_draw
    assert b_coder is not b_draw

    # 3. Interleaved token delivery: coder token arrives
    b_coder_next = chat.append_speaker_delta(
        speaker_role_id="coder",
        delta="    return 42\n",
    )
    # Must route to coder's existing bubble, NOT create a 3rd bubble
    assert b_coder_next is b_coder
    assert chat.message_count() == 2
    assert "return 42" in b_coder.content

    # 4. Interleaved token delivery: draw expert token arrives
    b_draw_next = chat.append_speaker_delta(
        speaker_role_id="draw_expert",
        delta="完成色彩填充。\n",
    )
    # Must route to draw expert's existing bubble, NOT create a 3rd bubble
    assert b_draw_next is b_draw
    assert chat.message_count() == 2
    assert "完成色彩填充" in b_draw.content

    # 5. Coder finishes
    chat.append_speaker_delta(
        speaker_role_id="coder",
        delta="",
        is_end=True,
    )
    assert "coder" not in chat._active_bubbles
    assert "draw_expert" in chat._active_bubbles
    assert chat.message_count() == 2

    # 6. Draw expert finishes
    chat.append_speaker_delta(
        speaker_role_id="draw_expert",
        delta="",
        is_end=True,
    )
    assert len(chat._active_bubbles) == 0
    assert chat.message_count() == 2
    assert b_coder.content == "def calculate():\n    return 42\n"
    assert b_draw.content == "开始绘制线稿...\n完成色彩填充。\n"


def test_speaker_badge_formatting(qtbot):
    item_coord = AssistantTextMessageItem(content="你好", speaker_role_id="coordinator")
    qtbot.addWidget(item_coord)
    assert "主持人" in item_coord.header_label.text() or "团队协调官" in item_coord.header_label.text()

    item_coder = AssistantTextMessageItem(content="代码", speaker_role_id="coder")
    qtbot.addWidget(item_coder)
    assert "代码专家" in item_coder.header_label.text()
    assert "💻" in item_coder.header_label.text()

    item_draw = AssistantTextMessageItem(content="插画", speaker_role_id="draw_expert")
    qtbot.addWidget(item_draw)
    assert "绘图专家" in item_draw.header_label.text()
    assert "🎨" in item_draw.header_label.text()


def test_clear_messages_resets_active_bubbles(qtbot):
    chat = ChatStreamView()
    qtbot.addWidget(chat)
    chat.show()

    chat.append_speaker_delta(
        speaker_role_id="coder",
        delta="运行中...",
        is_start=True,
    )
    assert len(chat._active_bubbles) == 1
    assert chat.message_count() == 1

    chat.clear_messages()
    assert len(chat._active_bubbles) == 0
    assert chat.message_count() == 0
