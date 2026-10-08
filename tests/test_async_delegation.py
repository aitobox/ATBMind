import asyncio
from unittest.mock import MagicMock
import pytest

from atbmind_core.harness.types import AgentEvent, AgentEventType, AgentMessage, Role
from atbmind_core.roles.delegation import DelegateTaskTool
from atbmind_core.roles.jobs import TeamJobStatus, TeamJobTracker
from atbmind_core.roles.schema import RobotRole
from atbmind_core.roles.team import RobotTeam


@pytest.fixture
def anyio_backend():
    return "asyncio"


def create_mock_team(roles: list[RobotRole]):
    team = MagicMock(spec=RobotTeam)
    role_map = {r.role_id: r for r in roles}
    team.get_role.side_effect = lambda rid: role_map.get(rid)
    team.collect_role_tools.return_value = []
    team.get_role_system_prompt.return_value = "提示词"
    team.list_role_ids.return_value = list(role_map.keys())
    return team


@pytest.mark.anyio
async def test_delegate_task_sync_mode_backward_compatibility():
    role = RobotRole(role_id="coder", name="程序员", description="编写代码")
    team = create_mock_team([role])
    job_tracker = TeamJobTracker()

    async def mock_stream_chat(*args, **kwargs):
        yield AgentEvent(AgentEventType.MESSAGE_START, {"message": AgentMessage(role=Role.ASSISTANT)})
        yield AgentEvent(AgentEventType.MESSAGE_DELTA, {"delta": "代码已生成"})
        yield AgentEvent(AgentEventType.MESSAGE_END, {"message": AgentMessage(role=Role.ASSISTANT, content="代码已生成")})

    mock_client = MagicMock()
    mock_client.stream_chat = mock_stream_chat

    tool = DelegateTaskTool(team=team, stream_client=mock_client, job_tracker=job_tracker)
    res = await tool.execute({
        "role_id": "coder",
        "task_description": "请编写加法函数",
        "async_mode": False,
    })

    assert not res.is_error
    assert "代码已生成" in res.content
    assert "【专家执行闭环通知】" in res.content
    assert res.metadata.get("subagent_role") == "coder"
    assert not job_tracker.has_active_jobs()


@pytest.mark.anyio
async def test_delegate_task_async_mode_immediate_return():
    role = RobotRole(role_id="researcher", name="调研员", description="搜集资料")
    team = create_mock_team([role])
    job_tracker = TeamJobTracker()

    callback_records = []

    def on_complete(role_id, task_desc, reply, followup):
        callback_records.append((role_id, task_desc, reply, followup))

    events_captured = []

    def on_event(event):
        events_captured.append(event)

    async def mock_stream_chat(*args, **kwargs):
        await asyncio.sleep(0.05)
        yield AgentEvent(AgentEventType.MESSAGE_START, {"message": AgentMessage(role=Role.ASSISTANT)})
        yield AgentEvent(AgentEventType.MESSAGE_DELTA, {"delta": "调研报告已完成"})
        yield AgentEvent(AgentEventType.MESSAGE_END, {"message": AgentMessage(role=Role.ASSISTANT, content="调研报告已完成")})

    mock_client = MagicMock()
    mock_client.stream_chat = mock_stream_chat

    tool = DelegateTaskTool(
        team=team,
        stream_client=mock_client,
        event_listener=on_event,
        job_tracker=job_tracker,
        completion_callback=on_complete,
    )

    # 1. Dispatch with async_mode=True
    res = await tool.execute({
        "role_id": "researcher",
        "task_description": "调研竞品功能",
        "async_mode": True,
    })

    # Non-blocking immediate return
    assert not res.is_error
    job_id = res.metadata.get("job_id")
    assert job_id is not None
    assert "异步派发" in res.content
    assert res.metadata.get("async") is True

    # Active job in tracker
    job = job_tracker.get_job(job_id)
    assert job is not None
    assert job.role_id == "researcher"
    assert job_tracker.is_role_busy("researcher") is True

    # 2. Wait for background task to finish
    await asyncio.sleep(0.15)

    # Completed in tracker
    job_after = job_tracker.get_job(job_id)
    assert job_after.status == TeamJobStatus.COMPLETED
    assert job_after.result == "调研报告已完成"
    assert not job_tracker.is_role_busy("researcher")

    # Callback was called
    assert len(callback_records) == 1
    assert callback_records[0][0] == "researcher"
    assert "调研报告已完成" in callback_records[0][2]

    # Events have speaker_role
    for ev in events_captured:
        assert ev.payload.get("speaker_role") == "researcher"


@pytest.mark.anyio
async def test_delegate_task_concurrent_multi_expert_dispatch():
    coder = RobotRole(role_id="coder", name="程序员")
    designer = RobotRole(role_id="designer", name="设计师")
    team = create_mock_team([coder, designer])
    job_tracker = TeamJobTracker()

    async def mock_stream_chat(*args, **kwargs):
        await asyncio.sleep(0.08)
        yield AgentEvent(AgentEventType.MESSAGE_END, {"message": AgentMessage(role=Role.ASSISTANT, content="并发完成")})

    mock_client = MagicMock()
    mock_client.stream_chat = mock_stream_chat

    tool = DelegateTaskTool(team=team, stream_client=mock_client, job_tracker=job_tracker)

    # Dispatch coder and designer in parallel
    r1 = await tool.execute({"role_id": "coder", "task_description": "写接口", "async_mode": True})
    r2 = await tool.execute({"role_id": "designer", "task_description": "画原型", "async_mode": True})

    assert r1.metadata["job_id"] != r2.metadata["job_id"]
    assert job_tracker.is_role_busy("coder") is True
    assert job_tracker.is_role_busy("designer") is True
    assert len(job_tracker.list_active_jobs()) == 2

    await asyncio.sleep(0.18)

    assert not job_tracker.has_active_jobs()
    assert job_tracker.get_job(r1.metadata["job_id"]).status == TeamJobStatus.COMPLETED
    assert job_tracker.get_job(r2.metadata["job_id"]).status == TeamJobStatus.COMPLETED


@pytest.mark.anyio
async def test_delegate_task_async_error_handling():
    role = RobotRole(role_id="tester", name="测试员")
    team = create_mock_team([role])
    job_tracker = TeamJobTracker()

    async def mock_stream_chat_failing(*args, **kwargs):
        await asyncio.sleep(0.02)
        raise RuntimeError("模拟子任务崩溃")
        yield  # unreachable

    mock_client = MagicMock()
    mock_client.stream_chat = mock_stream_chat_failing

    tool = DelegateTaskTool(team=team, stream_client=mock_client, job_tracker=job_tracker)
    res = await tool.execute({"role_id": "tester", "task_description": "执行压测", "async_mode": True})

    job_id = res.metadata["job_id"]
    await asyncio.sleep(0.08)

    job = job_tracker.get_job(job_id)
    assert job.status == TeamJobStatus.FAILED
    assert "模拟子任务崩溃" in job.error
    assert not job_tracker.has_active_jobs()
