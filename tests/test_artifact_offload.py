import json
import pytest
from atbmind_core.harness.types import (
    Role,
    ToolCall,
    AgentMessage,
    AgentEventType,
    AgentEvent,
    to_model_message,
)
from atbmind_core.harness.tools.base import AgentTool, ExecutionMode, ToolResult
from atbmind_core.harness.middleware.artifact_offload import ArtifactOffloadMiddleware
from atbmind_core.harness.loop import AgentContext, AgentLoopConfig, agent_loop
from pydantic import BaseModel

def test_tool_result_artifact_field():
    """ToolResult should accept and store artifact payload."""
    artifact_data = {"chart_type": "line", "points": [1, 2, 3]}
    res = ToolResult(
        content="Generated chart",
        is_error=False,
        metadata={"cost": 0.01},
        artifact=artifact_data,
    )
    assert res.content == "Generated chart"
    assert res.artifact == artifact_data
    assert res.artifact["chart_type"] == "line"

def test_to_model_message_strips_artifact_from_message():
    """to_model_message should strictly strip artifact from LLM context."""
    msg = AgentMessage(
        role=Role.TOOL,
        content="summary of chart",
        tool_call_id="call_999",
        name="draw_chart",
        metadata={"artifact": {"secret_large_data": "x" * 5000}},
    )
    model_msg = to_model_message(msg)
    assert model_msg["role"] == "tool"
    assert model_msg["content"] == "summary of chart"
    assert model_msg["tool_call_id"] == "call_999"
    assert "artifact" not in model_msg
    assert "secret_large_data" not in json.dumps(model_msg)

def test_to_model_message_from_tool_result():
    """to_model_message should also convert ToolResult directly without leaking artifact."""
    res = ToolResult(
        content="Result content",
        is_error=False,
        artifact={"internal_payload": [1, 2, 3]},
    )
    model_msg = to_model_message(res)
    assert model_msg["role"] == "tool"
    assert model_msg["content"] == "Result content"
    assert "artifact" not in model_msg

def test_middleware_offloads_large_ui_payload():
    """ArtifactOffloadMiddleware should extract payload >= 3000 chars with atbmind_ui."""
    middleware = ArtifactOffloadMiddleware(threshold=3000)

    heavy_data = {"key_" + str(i): "value_" + ("a" * 50) for i in range(100)}
    raw_payload = {
        "atbmind_ui": True,
        "ui_type": "draw_gallery",
        "title": "Generated 100 Artworks",
        "data": heavy_data,
    }
    raw_json = json.dumps(raw_payload, ensure_ascii=False)
    assert len(raw_json) >= 3000

    tool_res = ToolResult(content=raw_json, is_error=False)
    processed = middleware.process_tool_result(tool_res)

    # Payload extracted to artifact
    assert processed.artifact is not None
    assert processed.artifact["ui_type"] == "draw_gallery"
    assert processed.artifact["data"] == heavy_data

    # Content replaced by compact summary referencing artifact
    assert len(processed.content) < 500
    summary = json.loads(processed.content)
    assert summary["data_ref"] == "artifact"
    assert summary["type"] == "draw_gallery"
    assert "Generated 100 Artworks" in summary.get("summary", "")
    assert processed.metadata.get("offloaded") is True

def test_middleware_ignores_small_payload():
    """Payloads < 3000 chars should not be offloaded."""
    middleware = ArtifactOffloadMiddleware(threshold=3000)
    small_payload = {"atbmind_ui": True, "ui_type": "card", "msg": "hello"}
    raw_json = json.dumps(small_payload)
    assert len(raw_json) < 3000

    tool_res = ToolResult(content=raw_json, is_error=False)
    processed = middleware.process_tool_result(tool_res)

    assert processed.artifact is None
    assert processed.content == raw_json
    assert not processed.metadata.get("offloaded", False)

def test_middleware_ignores_large_payload_without_ui_flag():
    """Large payloads without atbmind_ui declaration should not be offloaded."""
    middleware = ArtifactOffloadMiddleware(threshold=3000)
    plain_large_json = json.dumps({"log_lines": ["info: line " + str(i) for i in range(300)]})
    assert len(plain_large_json) >= 3000

    tool_res = ToolResult(content=plain_large_json, is_error=False)
    processed = middleware.process_tool_result(tool_res)

    assert processed.artifact is None
    assert processed.content == plain_large_json

def test_middleware_handles_non_json_and_errors_gracefully():
    """Non-JSON large text and error results should pass through safely."""
    middleware = ArtifactOffloadMiddleware(threshold=3000)

    # 1. Non-JSON string >= 3000
    large_text = "Standard stdout output line\n" * 150
    assert len(large_text) >= 3000
    res_text = ToolResult(content=large_text, is_error=False)
    proc_text = middleware.process_tool_result(res_text)
    assert proc_text.artifact is None
    assert proc_text.content == large_text

    # 2. Error result with UI payload
    error_payload = json.dumps({"atbmind_ui": True, "data": "x" * 4000})
    res_err = ToolResult(content=error_payload, is_error=True)
    proc_err = middleware.process_tool_result(res_err)
    assert proc_err.artifact is None
    assert proc_err.content == error_payload

    # 3. Valid JSON but not a dict (e.g. list of items >= 3000)
    list_payload = json.dumps(["log_item_" + str(i) + ("x" * 20) for i in range(150)])
    assert len(list_payload) >= 3000
    res_list = ToolResult(content=list_payload, is_error=False)
    proc_list = middleware.process_tool_result(res_list)
    assert proc_list.artifact is None
    assert proc_list.content == list_payload

def test_middleware_nested_atbmind_ui_dict_and_long_summary_truncation():
    """Middleware should support nested atbmind_ui dict and truncate summary > 200 chars."""
    middleware = ArtifactOffloadMiddleware(threshold=3000)
    nested_payload = {
        "atbmind_ui": {"type": "interactive_dashboard"},
        "summary": "Important summary " + ("details " * 30),
        "data": {"points": [i for i in range(1000)]},
    }
    raw_json = json.dumps(nested_payload)
    assert len(raw_json) >= 3000

    tool_res = ToolResult(content=raw_json, is_error=False)
    processed = middleware.process_tool_result(tool_res)

    assert processed.artifact is not None
    assert processed.artifact["atbmind_ui"]["type"] == "interactive_dashboard"
    summary = json.loads(processed.content)
    assert summary["data_ref"] == "artifact"
    assert summary["type"] == "interactive_dashboard"
    assert len(summary["summary"]) <= 200
    assert summary["summary"].endswith("...")

@pytest.mark.asyncio
async def test_agent_loop_integration_with_middleware():
    """agent_loop should execute middleware and pass artifact in event & message metadata."""
    class DrawArgs(BaseModel):
        prompt: str

    class HeavyDrawTool(AgentTool):
        name = "heavy_draw"
        description = "Draws heavy UI card"
        parameters_schema = DrawArgs

        async def execute(self, args, context=None):
            payload = {
                "atbmind_ui": True,
                "ui_type": "image_result",
                "title": f"Art for {args['prompt']}",
                "images": ["data:image/png;base64," + ("A" * 3500)],
            }
            return ToolResult(content=json.dumps(payload))

    class MockStreamClient:
        def __init__(self):
            self.turn = 0

        async def stream_chat(self, messages, tools=None, system_prompt=None, temperature=None, cancellation_token=None):
            if self.turn == 0:
                # LLM calls tool
                self.turn += 1
                msg = AgentMessage(
                    role=Role.ASSISTANT,
                    content="Let me draw this.",
                    tool_calls=[ToolCall(id="tc_1", name="heavy_draw", arguments={"prompt": "mountain"})],
                )
            else:
                # Verify that tool message in LLM context does NOT have giant base64
                last_tool_msg = [m for m in messages if m.role == Role.TOOL][-1]
                assert len(last_tool_msg.content) < 500
                assert "AAAA" not in last_tool_msg.content
                msg = AgentMessage(role=Role.ASSISTANT, content="Drawing complete.")

            yield AgentEvent(AgentEventType.MESSAGE_START)
            yield AgentEvent(AgentEventType.MESSAGE_END, {"message": msg})

    client = MockStreamClient()
    tool = HeavyDrawTool()
    ctx = AgentContext(tools=[tool])
    cfg = AgentLoopConfig(stream_client=client)

    events = []
    async for ev in agent_loop([AgentMessage(role=Role.USER, content="Draw a mountain")], ctx, cfg):
        events.append(ev)

    # Verify TOOL_CALL_END event contains artifact
    tool_end_events = [e for e in events if e.type == AgentEventType.TOOL_CALL_END]
    assert len(tool_end_events) == 1
    end_payload = tool_end_events[0].payload
    assert "artifact" in end_payload
    assert end_payload["artifact"]["ui_type"] == "image_result"

    # Verify context messages
    tool_messages = [m for m in ctx.messages if m.role == Role.TOOL]
    assert len(tool_messages) == 1
    assert tool_messages[0].metadata.get("artifact") is not None
    assert tool_messages[0].metadata["artifact"]["ui_type"] == "image_result"
