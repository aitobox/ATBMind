import pytest

from atbmind_core.harness.types import AgentMessage, Role, ToolCall
from atbmind_core.roles.projection import (
    TeamThreadProjection,
    derive_member_session_id,
    parse_member_session_id,
    project_member_turn_to_room,
    tag_message_speaker,
)
from atbmind_core.storage.session_store import SessionStore


def test_derive_and_parse_member_session_id():
    room_id = "room_abc_123"
    role_id = "draw_expert"

    member_sid = derive_member_session_id(room_id, role_id)
    assert member_sid == "room_abc_123:member:draw_expert"

    parsed = parse_member_session_id(member_sid)
    assert parsed == ("room_abc_123", "draw_expert")

    # Invalid session id
    assert parse_member_session_id("random_plain_session") is None
    assert parse_member_session_id("room:other:role") is None


def test_tag_message_speaker():
    msg = AgentMessage(
        role=Role.ASSISTANT,
        content="Hello from expert",
        metadata={"custom_key": 42},
    )

    tagged = tag_message_speaker(
        msg,
        speaker_role="coder",
        speaker_name="代码专家",
        avatar="icon://coder.png",
    )

    assert tagged.metadata["speaker_role"] == "coder"
    assert tagged.metadata["speaker_name"] == "代码专家"
    assert tagged.metadata["avatar"] == "icon://coder.png"
    assert tagged.metadata["custom_key"] == 42


def test_project_member_turn_to_room_filtering():
    # Simulate a full subagent execution turn containing tool invocations
    messages = [
        AgentMessage(role=Role.USER, content="请画一只可爱的猫咪"),
        AgentMessage(
            role=Role.ASSISTANT,
            content=None,
            tool_calls=[ToolCall(id="call_1", name="generate_image", arguments={"prompt": "cute cat"})],
        ),
        AgentMessage(
            role=Role.TOOL,
            content="Saved image to data/cat.png",
            tool_call_id="call_1",
            name="generate_image",
        ),
        AgentMessage(
            role=Role.ASSISTANT,
            content="这是为您生成的可爱猫咪插画！",
            metadata={"ui_artifacts": [{"type": "image", "path": "data/cat.png"}]},
        ),
    ]

    projected = project_member_turn_to_room(
        member_messages=messages,
        room_session_id="room_101",
        speaker_role="draw_expert",
        speaker_name="绘图大师",
        avatar="icon://draw.png",
    )

    # Only the final assistant deliverable should be projected to the room
    assert len(projected) == 1
    proj_msg = projected[0]
    assert proj_msg.role == Role.ASSISTANT
    assert proj_msg.content == "这是为您生成的可爱猫咪插画！"
    assert proj_msg.metadata["speaker_role"] == "draw_expert"
    assert proj_msg.metadata["speaker_name"] == "绘图大师"
    assert proj_msg.metadata["projected_from_member"] is True
    assert proj_msg.metadata["origin_session_id"] == "room_101:member:draw_expert"
    # Preserves ui_artifacts
    assert proj_msg.metadata["ui_artifacts"] == [{"type": "image", "path": "data/cat.png"}]


def test_team_thread_projection_session_store_isolation():
    from atbmind_core.storage.schemas import MessageRecord, SessionRecord

    store = SessionStore(":memory:")
    room_sid = "room_primary"
    store.create_session(SessionRecord(session_id=room_sid, title="主群聊房间"))

    projection = TeamThreadProjection(store=store)

    # 1. Specialist writes into isolated sub-session
    member_sid = projection.get_or_create_member_session(room_sid, "analyst", title="数据分析师子会话")
    assert member_sid == "room_primary:member:analyst"

    # Save detailed messages into member session
    subagent_messages = [
        AgentMessage(role=Role.USER, content="计算 Q3 营收"),
        AgentMessage(
            role=Role.ASSISTANT,
            content=None,
            tool_calls=[ToolCall(id="t1", name="db_query", arguments={"sql": "select sum(revenue)"})],
        ),
        AgentMessage(role=Role.TOOL, content="15000000", tool_call_id="t1", name="db_query"),
        AgentMessage(role=Role.ASSISTANT, content="Q3 营收总额为 1,500 万元。"),
    ]

    for m in subagent_messages:
        store.append_message(
            MessageRecord(
                session_id=member_sid,
                role=m.role.value,
                content=m.content or "",
                plugin_payload=m.metadata,
            )
        )

    # Member session has 4 records
    mem_records = store.get_messages(member_sid)
    assert len(mem_records) == 4

    # 2. Project deliverables to room session
    projected = projection.project_to_room(
        room_session_id=room_sid,
        role_id="analyst",
        member_messages=subagent_messages,
        speaker_name="数据分析师",
    )

    assert len(projected) == 1

    # Room session now has exactly 1 projected record
    room_records = store.get_messages(room_sid)
    assert len(room_records) == 1
    assert room_records[0].content == "Q3 营收总额为 1,500 万元。"
    assert room_records[0].plugin_payload.get("speaker_role") == "analyst"
    assert room_records[0].plugin_payload.get("speaker_name") == "数据分析师"
    assert room_records[0].plugin_payload.get("projected_from_member") is True

