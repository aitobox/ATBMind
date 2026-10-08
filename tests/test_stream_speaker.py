"""Unit tests for SpeakerStreamEvent, EventBusQtBridge speaker stream, and ChatStreamView multi-expert stream bubbles (Issue #65)."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from atbmind_core.runtime.event_bus import (
    AsyncEventBus,
    SpeakerStreamEvent,
)
from apps.atbmind_desktop.bridge import EventBusQtBridge
from apps.atbmind_desktop.widgets.message_bubble import AssistantTextMessageItem
from apps.atbmind_desktop.widgets.chat_stream import ChatStreamView


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_speaker_stream_event_dataclass():
    event = SpeakerStreamEvent(
        speaker_role_id="draw_expert",
        speaker_name="AI画画专家",
        speaker_avatar="🎨",
        delta="正在生成草图...",
        is_start=True,
        is_end=False,
        message_id="msg-1",
    )
    assert event.speaker_role_id == "draw_expert"
    assert event.speaker_name == "AI画画专家"
    assert event.speaker_avatar == "🎨"
    assert event.delta == "正在生成草图..."
    assert event.is_start is True
    assert event.is_end is False
    assert event.source_id == "draw_expert"


@pytest.mark.asyncio
async def test_event_bus_and_bridge_speaker_stream(qtbot):
    bus = AsyncEventBus()
    bridge = EventBusQtBridge()
    bridge.attach_bus(bus)

    with qtbot.waitSignal(bridge.speaker_stream_received, timeout=1000) as stream_signal:
        await bus.publish(
            SpeakerStreamEvent(
                speaker_role_id="coder_expert",
                speaker_name="代码专家",
                speaker_avatar="💻",
                delta="def solve(): pass",
                is_start=False,
                is_end=True,
            )
        )

    payload = stream_signal.args[0]
    assert payload["speaker_role_id"] == "coder_expert"
    assert payload["speaker_name"] == "代码专家"
    assert payload["speaker_avatar"] == "💻"
    assert payload["delta"] == "def solve(): pass"
    assert payload["is_end"] is True


def test_assistant_text_message_item_speaker_badge_and_append(qtbot):
    item = AssistantTextMessageItem(
        content="初始内容",
        speaker_role_id="draw_expert",
        speaker_name="AI画画专家",
        speaker_avatar="🎨",
    )
    qtbot.addWidget(item)
    item.show()

    assert item.speaker_role_id == "draw_expert"
    assert item.speaker_name == "AI画画专家"
    assert "AI画画专家" in item.header_label.text()
    assert "🎨" in item.header_label.text()

    # Append streaming text
    item.append_text("，追加了一段描述")
    assert item.content == "初始内容，追加了一段描述"
    assert item.msg_label.text() == "初始内容，追加了一段描述"


def test_chat_stream_view_multi_expert_stream_routing(qtbot):
    chat = ChatStreamView()
    qtbot.addWidget(chat)
    chat.show()

    assert chat.message_count() == 0

    # 1. Coordinator starts streaming
    b1 = chat.append_speaker_delta(
        speaker_role_id="coordinator",
        speaker_name="团队协调官",
        delta="你好！我正在为你统筹任务。",
        speaker_avatar="✦",
        is_start=True,
    )
    assert chat.message_count() == 1
    assert b1.content == "你好！我正在为你统筹任务。"

    # Append to same speaker
    b1_next = chat.append_speaker_delta(
        speaker_role_id="coordinator",
        speaker_name="团队协调官",
        delta="现在将绘图任务分配给画画专家。",
    )
    assert b1_next is b1
    assert chat.message_count() == 1
    assert "分配给画画专家" in b1.content

    # 2. Draw expert takes over -> MUST smoothly create a new bubble for Draw Expert
    b2 = chat.append_speaker_delta(
        speaker_role_id="draw_expert",
        speaker_name="AI画画专家",
        delta="收到需求！正在进行构图。",
        speaker_avatar="🎨",
        is_start=True,
    )
    assert b2 is not b1
    assert chat.message_count() == 2
    assert b2.speaker_role_id == "draw_expert"
    assert "构图" in b2.content

    # Draw expert finishes
    chat.append_speaker_delta(
        speaker_role_id="draw_expert",
        speaker_name="AI画画专家",
        delta="绘制完成！",
        is_end=True,
    )
    assert "绘制完成！" in b2.content
    assert chat.message_count() == 2

    # 3. Add assistant message with speaker metadata
    b3 = chat.add_assistant_message(
        "最终收口总结：一切顺利。",
        speaker_role_id="coordinator",
        speaker_name="团队协调官",
        speaker_avatar="✦",
    )
    assert chat.message_count() == 3
    assert b3.speaker_role_id == "coordinator"
    assert "团队协调官" in b3.header_label.text()
