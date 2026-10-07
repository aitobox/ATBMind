import pytest
from unittest.mock import AsyncMock, MagicMock
from atbmind_core.roles.team import RobotTeam
from atbmind_core.roles.schema import RobotRole
from atbmind_core.skills.schema import Skill, SkillMetadata
from atbmind_core.harness.types import AgentEvent, AgentEventType, AgentMessage, Role

@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.mark.anyio
async def test_delegate_task_execution():
    team = MagicMock(spec=RobotTeam)
    specialist = RobotRole(
        role_id="specialist",
        name="专员",
        description="专业执行",
        system_prompt="专员提示词",
        skills=[],
    )
    team.get_role.return_value = specialist
    team.collect_role_tools.return_value = []
    team.get_role_system_prompt.return_value = "专员提示词"

    mock_stream_client = MagicMock()
    # Mock stream_chat returning an assistant reply
    async def mock_stream_chat(*args, **kwargs):
        yield AgentEvent(AgentEventType.MESSAGE_START, {"message": AgentMessage(role=Role.ASSISTANT)})
        yield AgentEvent(AgentEventType.MESSAGE_DELTA, {"delta": "任务已完成"})
        yield AgentEvent(AgentEventType.MESSAGE_END, {"message": AgentMessage(role=Role.ASSISTANT, content="任务已完成")})
    mock_stream_client.stream_chat = mock_stream_chat

    from atbmind_core.roles.delegation import DelegateTaskTool
    tool = DelegateTaskTool(team=team, stream_client=mock_stream_client)
    res = await tool.execute({"role_id": "specialist", "task_description": "请处理数据"})
    assert not res.is_error
    assert "任务已完成" in res.content

@pytest.mark.anyio
async def test_delegate_task_unknown_role():
    team = MagicMock(spec=RobotTeam)
    team.get_role.return_value = None
    team.list_role_ids.return_value = ["draw_expert"]

    mock_stream_client = MagicMock()
    from atbmind_core.roles.delegation import DelegateTaskTool
    tool = DelegateTaskTool(team=team, stream_client=mock_stream_client)
    res = await tool.execute({"role_id": "nonexistent", "task_description": "abc"})
    assert res.is_error
    assert "不存在角色" in res.content
    assert "draw_expert" in res.content

def test_team_build_coordinator_system_prompt():
    team = RobotTeam(leader_role_id="coord")
    role_coord = RobotRole(role_id="coord", name="协调员", system_prompt="基础提示词")
    role_expert = RobotRole(role_id="draw", name="画画专家", description="专业修图")
    team.role_registry.register_role(role_coord)
    team.role_registry.register_role(role_expert)

    prompt = team.build_coordinator_system_prompt()
    assert "基础提示词" in prompt
    assert "draw" in prompt
    assert "画画专家" in prompt
