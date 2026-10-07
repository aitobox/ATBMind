"""
Tests for Antigravity-grade shell and schedule runtime tools:
- RunCommandTool (run_command)
- ManageTaskTool (manage_task)
- ScheduleTool (schedule)
"""

import json
from pathlib import Path
import pytest

from atbmind_core.runtime.event_bus import AsyncEventBus
from atbmind_core.runtime.tasks import TaskManager
from atbmind_core.runtime.tools.shell_tools import RunCommandTool, ManageTaskTool
from atbmind_core.runtime.tools.schedule_tools import ScheduleTool


# ---------------- 1. Basic Flow from Brief ----------------

@pytest.mark.asyncio
async def test_run_command_and_manage_task_tools(tmp_path: Path):
    bus = AsyncEventBus()
    tm = TaskManager(event_bus=bus, log_dir=tmp_path)
    run_tool = RunCommandTool(task_manager=tm)
    manage_tool = ManageTaskTool(task_manager=tm)

    # 1. 运行同步命令
    res = await run_tool.execute_async(CommandLine="echo 'hello tool'", Cwd=str(tmp_path), WaitMsBeforeAsync=2000)
    assert res.success is True
    assert "hello tool" in res.output

    # 2. 运行后台慢命令
    slow_res = await run_tool.execute_async(CommandLine="sleep 5", Cwd=str(tmp_path), WaitMsBeforeAsync=100)
    assert slow_res.success is True
    assert "task_id" in slow_res.output or "task-" in slow_res.output

    # 3. manage_task list
    list_res = await manage_tool.execute_async(Action="list")
    assert list_res.success is True

    # Clean up
    await tm.shutdown()


@pytest.mark.asyncio
async def test_schedule_tool():
    bus = AsyncEventBus()
    tm = TaskManager(event_bus=bus)
    sched_tool = ScheduleTool(task_manager=tm)
    res = await sched_tool.execute_async(Prompt="Do periodic check", DurationSeconds=60, TimerCondition="never")
    assert res.success is True
    assert "timer-" in res.output or "scheduled" in res.output.lower()

    # Clean up
    await tm.shutdown()


# ---------------- 2. RunCommandTool In-depth Tests ----------------

@pytest.mark.asyncio
async def test_run_command_sync_failure(tmp_path: Path):
    bus = AsyncEventBus()
    tm = TaskManager(event_bus=bus, log_dir=tmp_path)
    run_tool = RunCommandTool(task_manager=tm)

    res = await run_tool.execute_async(CommandLine="exit 42", Cwd=str(tmp_path), WaitMsBeforeAsync=2000)
    assert res.success is False
    assert res.is_error is True
    assert "42" in res.output
    assert res.metadata.get("exit_code") == 42

    await tm.shutdown()


@pytest.mark.asyncio
async def test_run_command_invalid_cwd(tmp_path: Path):
    bus = AsyncEventBus()
    tm = TaskManager(event_bus=bus, log_dir=tmp_path)
    run_tool = RunCommandTool(task_manager=tm)

    non_existent = tmp_path / "does_not_exist_dir"
    res = await run_tool.execute_async(CommandLine="echo 1", Cwd=str(non_existent), WaitMsBeforeAsync=1000)
    assert res.success is False
    assert "directory" in res.error.lower()

    await tm.shutdown()


@pytest.mark.asyncio
async def test_run_command_empty_command(tmp_path: Path):
    bus = AsyncEventBus()
    tm = TaskManager(event_bus=bus, log_dir=tmp_path)
    run_tool = RunCommandTool(task_manager=tm)

    res = await run_tool.execute_async(CommandLine="   ", Cwd=str(tmp_path))
    assert res.success is False
    assert "command" in res.error.lower()

    await tm.shutdown()


@pytest.mark.asyncio
async def test_run_command_persistent_terminal(tmp_path: Path):
    bus = AsyncEventBus()
    tm = TaskManager(event_bus=bus, log_dir=tmp_path)
    run_tool = RunCommandTool(task_manager=tm)

    # First command: export variable in persistent terminal
    res1 = await run_tool.execute_async(
        CommandLine="export GREETING='hello from persistent terminal'",
        Cwd=str(tmp_path),
        RunPersistent=True,
        RequestedTerminalID="term-test-1",
        WaitMsBeforeAsync=2000,
    )
    assert res1.success is True

    # Second command: read exported variable in the same terminal
    res2 = await run_tool.execute_async(
        CommandLine="echo $GREETING",
        Cwd=str(tmp_path),
        RunPersistent=True,
        RequestedTerminalID="term-test-1",
        WaitMsBeforeAsync=2000,
    )
    assert res2.success is True
    assert "hello from persistent terminal" in res2.output

    await tm.shutdown()


@pytest.mark.asyncio
async def test_run_command_parameter_normalization(tmp_path: Path):
    bus = AsyncEventBus()
    tm = TaskManager(event_bus=bus, log_dir=tmp_path)
    run_tool = RunCommandTool(task_manager=tm)

    # Use snake_case keys
    res = await run_tool.execute_async(
        command="echo 'normalized params'",
        cwd=str(tmp_path),
        wait_ms=2000,
    )
    assert res.success is True
    assert "normalized params" in res.output

    await tm.shutdown()


# ---------------- 3. ManageTaskTool In-depth Tests ----------------

@pytest.mark.asyncio
async def test_manage_task_actions(tmp_path: Path):
    bus = AsyncEventBus()
    tm = TaskManager(event_bus=bus, log_dir=tmp_path)
    run_tool = RunCommandTool(task_manager=tm)
    manage_tool = ManageTaskTool(task_manager=tm)

    # Launch background task
    bg_res = await run_tool.execute_async(CommandLine="sleep 10", Cwd=str(tmp_path), WaitMsBeforeAsync=100)
    assert bg_res.success is True
    task_id = bg_res.metadata["task_id"]

    # 1. Action = status
    status_res = await manage_tool.execute_async(Action="status", TaskId=task_id)
    assert status_res.success is True
    assert task_id in status_res.output
    status_data = json.loads(status_res.output)
    assert status_data["status"] == "running"

    # 2. Action = kill
    kill_res = await manage_tool.execute_async(Action="kill", TaskId=task_id)
    assert kill_res.success is True
    assert task_id in kill_res.output

    # Check status again -> killed
    status_res2 = await manage_tool.execute_async(Action="status", TaskId=task_id)
    assert status_res2.success is True
    status_data2 = json.loads(status_res2.output)
    assert status_data2["status"] == "killed"

    # 3. Action = status on nonexistent task
    bad_res = await manage_tool.execute_async(Action="status", TaskId="task-nonexistent")
    assert bad_res.success is False

    # 4. Action without required TaskId
    no_id_res = await manage_tool.execute_async(Action="kill")
    assert no_id_res.success is False
    assert "taskid" in no_id_res.error.lower()

    await tm.shutdown()


@pytest.mark.asyncio
async def test_manage_task_send_input(tmp_path: Path):
    bus = AsyncEventBus()
    tm = TaskManager(event_bus=bus, log_dir=tmp_path)
    run_tool = RunCommandTool(task_manager=tm)
    manage_tool = ManageTaskTool(task_manager=tm)

    # Start cat process waiting for input
    bg_res = await run_tool.execute_async(CommandLine="cat", Cwd=str(tmp_path), WaitMsBeforeAsync=100)
    assert bg_res.success is True
    task_id = bg_res.metadata["task_id"]

    # Send input
    input_res = await manage_tool.execute_async(Action="send_input", TaskId=task_id, Input="hello cat\n")
    assert input_res.success is True

    # Kill task
    await manage_tool.execute_async(Action="kill", TaskId=task_id)
    await tm.shutdown()


# ---------------- 4. ScheduleTool In-depth Tests ----------------

@pytest.mark.asyncio
async def test_schedule_tool_one_shot_and_cancel():
    bus = AsyncEventBus()
    tm = TaskManager(event_bus=bus)
    sched_tool = ScheduleTool(task_manager=tm)
    manage_tool = ManageTaskTool(task_manager=tm)

    # Schedule a timer for 120s
    res = await sched_tool.execute_async(Prompt="Reminder to drink water", DurationSeconds=120)
    assert res.success is True
    timer_id = res.metadata["timer_id"]
    assert "timer-" in timer_id

    # Check status via manage_tool
    status_res = await manage_tool.execute_async(Action="status", TaskId=timer_id)
    assert status_res.success is True
    status_data = json.loads(status_res.output)
    assert status_data["status"] == "running"
    assert status_data["prompt"] == "Reminder to drink water"

    # Cancel via manage_tool
    kill_res = await manage_tool.execute_async(Action="kill", TaskId=timer_id)
    assert kill_res.success is True

    await tm.shutdown()


@pytest.mark.asyncio
async def test_schedule_tool_recurring_cron():
    bus = AsyncEventBus()
    tm = TaskManager(event_bus=bus)
    sched_tool = ScheduleTool(task_manager=tm)
    manage_tool = ManageTaskTool(task_manager=tm)

    # Schedule a recurring cron
    res = await sched_tool.execute_async(
        Prompt="Check deploy status",
        CronExpression="*/5 * * * *",
        MaxIterations=3,
        IsDaemon=False,
    )
    assert res.success is True
    cron_id = res.metadata["timer_id"]
    assert "cron-" in cron_id

    # Check status
    status_res = await manage_tool.execute_async(Action="status", TaskId=cron_id)
    assert status_res.success is True
    status_data = json.loads(status_res.output)
    assert status_data["is_cron"] is True
    assert status_data["cron_expr"] == "*/5 * * * *"

    # Kill cron
    kill_res = await manage_tool.execute_async(Action="kill", TaskId=cron_id)
    assert kill_res.success is True

    await tm.shutdown()


@pytest.mark.asyncio
async def test_schedule_tool_validation():
    bus = AsyncEventBus()
    tm = TaskManager(event_bus=bus)
    sched_tool = ScheduleTool(task_manager=tm)

    # Error: neither DurationSeconds nor CronExpression
    res1 = await sched_tool.execute_async(Prompt="No schedule specified")
    assert res1.success is False
    assert "exactly one" in res1.error.lower()

    # Error: both DurationSeconds and CronExpression
    res2 = await sched_tool.execute_async(
        Prompt="Both specified",
        DurationSeconds=60,
        CronExpression="* * * * *",
    )
    assert res2.success is False
    assert "not both" in res2.error.lower()

    # Error: empty prompt
    res3 = await sched_tool.execute_async(Prompt="  ", DurationSeconds=10)
    assert res3.success is False
    assert "prompt" in res3.error.lower()

    # Error: invalid cron expression
    res4 = await sched_tool.execute_async(Prompt="Bad cron", CronExpression="invalid cron")
    assert res4.success is False
    assert "cron" in res4.error.lower()

    await tm.shutdown()


# ---------------- 5. OpenAI Schema Generation ----------------

def test_tools_openai_schema():
    bus = AsyncEventBus()
    tm = TaskManager(event_bus=bus)

    run_tool = RunCommandTool(task_manager=tm)
    manage_tool = ManageTaskTool(task_manager=tm)
    sched_tool = ScheduleTool(task_manager=tm)

    for tool in [run_tool, manage_tool, sched_tool]:
        schema = tool.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == tool.name
        assert "description" in schema["function"]
        assert "parameters" in schema["function"]
        assert "properties" in schema["function"]["parameters"]


# ---------------- 6. Standard execute & Dict args ----------------

@pytest.mark.asyncio
async def test_tools_standard_execute_and_dict_args(tmp_path: Path):
    bus = AsyncEventBus()
    tm = TaskManager(event_bus=bus, log_dir=tmp_path)
    run_tool = RunCommandTool(task_manager=tm)
    manage_tool = ManageTaskTool(task_manager=tm)
    sched_tool = ScheduleTool(task_manager=tm)

    # 1. run_command using .execute(dict)
    res1 = await run_tool.execute({"CommandLine": "echo 'from dict'", "Cwd": str(tmp_path), "WaitMsBeforeAsync": 2000})
    assert res1.success is True
    assert "from dict" in res1.output

    # 2. manage_task using .execute(dict)
    res2 = await manage_tool.execute({"Action": "list"})
    assert res2.success is True
    assert "tasks" in res2.output

    # 3. schedule using .execute(dict)
    res3 = await sched_tool.execute({"Prompt": "Check", "DurationSeconds": 30})
    assert res3.success is True
    assert "timer-" in res3.output

    # Clean up
    await tm.shutdown()


@pytest.mark.asyncio
async def test_schedule_tool_duplicate_condition_conflict():
    bus = AsyncEventBus()
    tm = TaskManager(event_bus=bus)
    sched_tool = ScheduleTool(task_manager=tm)

    # First timer with condition 'any'
    res1 = await sched_tool.execute_async(Prompt="Timer 1", DurationSeconds=60, TimerCondition="any")
    assert res1.success is True

    # Second timer with condition 'any' should fail gracefully
    res2 = await sched_tool.execute_async(Prompt="Timer 2", DurationSeconds=60, TimerCondition="any")
    assert res2.success is False
    assert "already active" in res2.error

    await tm.shutdown()


@pytest.mark.asyncio
async def test_run_command_default_task_manager(tmp_path: Path):
    # Instantiation without passing task_manager should succeed and function properly
    tool = RunCommandTool()
    assert tool.task_manager is not None
    res = await tool.execute_async(CommandLine="echo 'default tm'", Cwd=str(tmp_path), WaitMsBeforeAsync=2000)
    assert res.success is True
    assert "default tm" in res.output
    await tool.task_manager.shutdown()

