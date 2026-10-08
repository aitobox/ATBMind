import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from atbmind_core.roles.team import RobotTeam, COORDINATOR_ALLOWED_TOOLS
from atbmind_core.roles.schema import RobotRole
from atbmind_core.roles.delegation import DelegateTaskTool, ListRolesTool, compose_followup
from atbmind_core.harness.tools.base import AgentTool, ToolResult


@pytest.fixture
def anyio_backend():
    return "asyncio"


class DummyHeavyTool(AgentTool):
    name = "generate_image"
    description = "重型生图工具"

    async def execute(self, args, context=None):
        return ToolResult(content="heavy")


class DummyFileTool(AgentTool):
    name = "write_to_file"
    description = "重型写文件工具"

    async def execute(self, args, context=None):
        return ToolResult(content="heavy file")


class DummyAllowedTool(AgentTool):
    name = "get_current_time"
    description = "时间查询工具"

    async def execute(self, args, context=None):
        return ToolResult(content="2026-10-08")


def test_coordinator_tool_whitelist_enforcement():
    team = RobotTeam(leader_role_id="coordinator")
    coord_role = RobotRole(
        role_id="coordinator",
        name="团队协调官",
        description="协调",
        system_prompt="协调员",
    )
    team.role_registry.register_role(coord_role)

    # Mock collect_role_tools to simulate heavy tools mistakenly bound to coordinator
    team.collect_role_tools = MagicMock(return_value=[
        DummyHeavyTool(),
        DummyFileTool(),
        DummyAllowedTool(),
    ])

    mock_stream_client = MagicMock()
    session = team.create_coordinator_session(
        session_id="test-session",
        stream_client=mock_stream_client,
    )

    tool_names = [t.name for t in session.tools]
    # Whitelist check: should contain delegate_task, list_roles, get_current_time
    assert "delegate_task" in tool_names
    assert "list_roles" in tool_names
    assert "get_current_time" in tool_names
    # Heavy execution tools MUST be stripped out
    assert "generate_image" not in tool_names
    assert "write_to_file" not in tool_names
    for name in tool_names:
        assert name in COORDINATOR_ALLOWED_TOOLS


@pytest.mark.anyio
async def test_list_roles_tool():
    team = RobotTeam(leader_role_id="coordinator")
    team.role_registry.register_role(RobotRole(role_id="coordinator", name="协调官", description="协调"))
    team.role_registry.register_role(RobotRole(role_id="draw_expert", name="画画专家", description="专业AI生图"))

    tool = ListRolesTool(team=team)
    result = await tool.execute({})
    assert not result.is_error
    data = json.loads(result.content)
    # Coordinator themselves shouldn't be listed as a sub-expert or should be distinguished
    role_ids = [r["role_id"] for r in data]
    assert "draw_expert" in role_ids
    assert any(r["name"] == "画画专家" for r in data)


def test_compose_followup_function():
    prompt = compose_followup(
        role_id="draw_expert",
        role_name="画画专家",
        task_description="请绘制两张赛博朋克风格海报",
        subagent_result="已生成 2 张 16:9 图像，存储于 data/images/cyber_01.png",
        max_sentences=3,
    )
    assert "画画专家" in prompt
    assert "3 句" in prompt or "3句" in prompt or "三句" in prompt
    assert "禁止原样复述" in prompt or "严禁复述" in prompt
    assert "已完成" in prompt or "交付" in prompt


def test_coordinator_system_prompt_anti_pass_through():
    team = RobotTeam(leader_role_id="coordinator")
    team.role_registry.register_role(RobotRole(role_id="coordinator", name="协调官", description="协调"))
    team.role_registry.register_role(RobotRole(role_id="expert", name="专家", description="测试"))

    prompt = team.build_coordinator_system_prompt()
    # Check Anti-Pass-Through rules injected
    assert "禁止" in prompt
    assert "任务说明书" in prompt or "任务书" in prompt
    assert "收口" in prompt or "闭环" in prompt


def test_coordinator_role_configs_exist_and_consistent():
    yaml_file = Path("roles/coordinator/role.yaml")
    json_file = Path("roles/coordinator.json")
    assert yaml_file.exists()
    assert json_file.exists()

    content_yaml = yaml_file.read_text(encoding="utf-8")
    content_json = json_file.read_text(encoding="utf-8")
    assert "Anti-Pass-Through" in content_yaml or "禁止原样转发" in content_yaml or "禁止直接转发" in content_yaml
    assert "Anti-Pass-Through" in content_json or "禁止原样转发" in content_json or "禁止直接转发" in content_json
