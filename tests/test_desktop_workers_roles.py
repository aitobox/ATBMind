import pytest
from unittest.mock import MagicMock
from pathlib import Path
from apps.atbmind_desktop.workers import GenerationWorker
from atbmind_core.roles.team import RobotTeam

def test_generation_worker_role_attributes():
    worker = GenerationWorker(
        session_id="test_sess",
        prompt="测试提示词",
        active_role_id="draw_expert",
    )
    assert worker.session_id == "test_sess"
    assert worker.active_role_id == "draw_expert"
    # Backwards compatibility check
    assert worker.active_plugin_id == "draw_expert"

def test_generation_worker_team_setup():
    worker = GenerationWorker(
        session_id="test_sess",
        prompt="测试团队设置",
        use_harness=True,
    )
    assert worker.use_harness is True


def test_generation_worker_skill_manager_integration():
    from atbmind_core.skills.manager import SkillManager
    from atbmind_core.skills.registry import SkillRegistry

    mock_mgr = MagicMock(spec=SkillManager)
    mock_reg = SkillRegistry()
    mock_mgr.skill_registry = mock_reg

    worker = GenerationWorker(
        session_id="test_sess",
        prompt="测试提示词",
        skill_manager=mock_mgr,
    )
    assert hasattr(worker, "skill_manager")
    assert worker.skill_manager is mock_mgr


@pytest.mark.asyncio
async def test_generation_worker_discovers_skills_via_skill_manager():
    from atbmind_core.skills.manager import SkillManager
    from atbmind_core.skills.registry import SkillRegistry

    mock_mgr = MagicMock(spec=SkillManager)
    mock_reg = SkillRegistry()
    mock_mgr.skill_registry = mock_reg

    worker = GenerationWorker(
        session_id="test_sess",
        prompt="测试提示词",
        skill_manager=mock_mgr,
    )
    mock_client = MagicMock()
    async def mock_stream(*args, **kwargs):
        from atbmind_core.harness.types import AgentEvent, AgentEventType, AgentMessage, Role
        yield AgentEvent(AgentEventType.MESSAGE_START)
        yield AgentEvent(AgentEventType.MESSAGE_END, {"message": AgentMessage(role=Role.ASSISTANT, content="done")})
    mock_client.stream_chat = mock_stream
    worker.llm_client = mock_client

    await worker._async_harness_run()
    mock_mgr.discover_all.assert_called_once()
