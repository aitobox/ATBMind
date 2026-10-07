"""Tests for TaskManager: Background tasks, persistent terminals, and scheduler."""

import asyncio
from datetime import datetime, timedelta
import os
from pathlib import Path
import pytest

from atbmind_core.runtime.event_bus import (
    AsyncEventBus,
    TaskOutputEvent,
    TaskStatusChangedEvent,
    TimerFiredEvent,
)
from atbmind_core.runtime.tasks import (
    TaskManager,
    TaskStatus,
    cron_match,
    get_next_cron_run,
    parse_cron_field,
)


@pytest.mark.asyncio
async def test_fast_command_runs_synchronously(tmp_path: Path):
    bus = AsyncEventBus()
    manager = TaskManager(event_bus=bus, log_dir=tmp_path)
    result = await manager.run_command(
        "echo 'sync test'",
        cwd=str(tmp_path),
        wait_ms_before_async=2000,
    )
    assert result["is_async"] is False
    assert "sync test" in result["output"]
    assert result["exit_code"] == 0
    await manager.shutdown()


@pytest.mark.asyncio
async def test_slow_command_transitions_to_background_and_kill(tmp_path: Path):
    bus = AsyncEventBus()
    status_events = []
    bus.subscribe(TaskStatusChangedEvent, lambda e: status_events.append(e))

    manager = TaskManager(event_bus=bus, log_dir=tmp_path)
    # Slow command: sleep 10
    result = await manager.run_command(
        "sleep 10",
        cwd=str(tmp_path),
        wait_ms_before_async=200,
    )
    assert result["is_async"] is True
    task_id = result["task_id"]

    status_info = manager.get_task_status(task_id)
    assert status_info is not None
    assert status_info["status"] == TaskStatus.RUNNING.value

    # Terminate task
    kill_res = await manager.kill_task(task_id)
    assert kill_res is True
    await asyncio.sleep(0.1)

    status_after = manager.get_task_status(task_id)
    assert status_after["status"] in (TaskStatus.KILLED.value, TaskStatus.DONE.value)

    # Check status changed event was emitted
    assert any(e.source_id == task_id for e in status_events)
    await manager.shutdown()


@pytest.mark.asyncio
async def test_scheduler_one_shot_timer():
    bus = AsyncEventBus()
    fired = []
    bus.subscribe(TimerFiredEvent, lambda e: fired.append(e.prompt))
    manager = TaskManager(event_bus=bus)

    timer_id = await manager.schedule_timer("Wakeup alert", duration_s=0.1)
    assert timer_id.startswith("timer-")
    await asyncio.sleep(0.2)

    assert len(fired) == 1
    assert fired[0] == "Wakeup alert"
    await manager.shutdown()


@pytest.mark.asyncio
async def test_timer_early_cancellation_any():
    bus = AsyncEventBus()
    fired = []
    bus.subscribe(TimerFiredEvent, lambda e: fired.append(e.prompt))
    manager = TaskManager(event_bus=bus)

    # Set timer for 0.5s with condition "any"
    timer_id = await manager.schedule_timer("Cancelled timer", duration_s=0.5, condition="any")

    await asyncio.sleep(0.05)
    # Simulate an incoming event from any task
    await bus.publish(TaskStatusChangedEvent(source_id="task-999", old_status="running", new_status="done"))

    # Wait past 0.5s
    await asyncio.sleep(0.55)

    # Timer should have been cancelled early and never fired
    assert len(fired) == 0
    status = manager.get_timer_status(timer_id)
    assert status["status"] in ("cancelled", "killed")
    await manager.shutdown()


@pytest.mark.asyncio
async def test_timer_early_cancellation_specific_sender():
    bus = AsyncEventBus()
    fired = []
    bus.subscribe(TimerFiredEvent, lambda e: fired.append(e.prompt))
    manager = TaskManager(event_bus=bus)

    # Timer only cancelled if message from "task-target"
    timer_id = await manager.schedule_timer("Specific cancel", duration_s=0.3, condition="task-target")

    # Event from a DIFFERENT task should not cancel it
    await bus.publish(TaskStatusChangedEvent(source_id="task-other", old_status="running", new_status="done"))
    await asyncio.sleep(0.05)

    # Event from matching task cancels it
    await bus.publish(TaskStatusChangedEvent(source_id="task-target", old_status="running", new_status="done"))
    await asyncio.sleep(0.35)

    assert len(fired) == 0
    await manager.shutdown()


@pytest.mark.asyncio
async def test_timer_duplicate_condition_conflict():
    bus = AsyncEventBus()
    manager = TaskManager(event_bus=bus)

    t1 = await manager.schedule_timer("Timer 1", duration_s=2.0, condition="any")
    with pytest.raises(ValueError, match="already active"):
        await manager.schedule_timer("Timer 2", duration_s=2.0, condition="any")

    # Cancel t1 to test task-123 conflict
    await manager.cancel_timer(t1)

    t3 = await manager.schedule_timer("Timer 3", duration_s=2.0, condition="task-123")
    with pytest.raises(ValueError, match="already active"):
        await manager.schedule_timer("Timer 4", duration_s=2.0, condition="task-123")
    with pytest.raises(ValueError, match="already active"):
        await manager.schedule_timer("Timer 5", duration_s=2.0, condition="any")


    await manager.shutdown()


@pytest.mark.asyncio
async def test_manage_task_list_and_status(tmp_path: Path):
    bus = AsyncEventBus()
    manager = TaskManager(event_bus=bus, log_dir=tmp_path)

    # Start a slow command
    res = await manager.run_command("sleep 5", cwd=str(tmp_path), wait_ms_before_async=100)
    task_id = res["task_id"]

    # manage_task list
    list_res = await manager.manage_task(action="list")
    assert isinstance(list_res, dict)
    assert any(t["task_id"] == task_id for t in list_res["tasks"])

    # manage_task status
    status_res = await manager.manage_task(action="status", task_id=task_id)
    assert status_res["task_id"] == task_id
    assert status_res["status"] == TaskStatus.RUNNING.value

    # manage_task kill
    kill_res = await manager.manage_task(action="kill", task_id=task_id)
    assert kill_res["success"] is True

    await asyncio.sleep(0.1)
    status_res2 = await manager.manage_task(action="status", task_id=task_id)
    assert status_res2["status"] in (TaskStatus.KILLED.value, TaskStatus.DONE.value)

    await manager.shutdown()


@pytest.mark.asyncio
async def test_manage_task_send_input(tmp_path: Path):
    bus = AsyncEventBus()
    manager = TaskManager(event_bus=bus, log_dir=tmp_path)

    # Python script reading stdin and printing
    py_code = "import sys; line = sys.stdin.readline().strip(); print(f'RECV:{line}', flush=True)"
    cmd = f'python3 -u -c "{py_code}"'

    res = await manager.run_command(cmd, cwd=str(tmp_path), wait_ms_before_async=200)
    task_id = res["task_id"]

    # Send input via manage_task
    input_res = await manager.manage_task(action="send_input", task_id=task_id, input_text="greetings\n")
    assert input_res["success"] is True

    # Wait for process to finish
    await asyncio.sleep(0.3)
    log_file = tmp_path / f"{task_id}.log"
    assert log_file.exists()
    content = log_file.read_text()
    assert "RECV:greetings" in content

    await manager.shutdown()


@pytest.mark.asyncio
async def test_persistent_terminal_preserves_env(tmp_path: Path):
    bus = AsyncEventBus()
    manager = TaskManager(event_bus=bus, log_dir=tmp_path)

    # Invocations in persistent terminal share exported variables
    res1 = await manager.run_command(
        "export ATBMIND_TEST_VAR='alpha_beta'",
        cwd=str(tmp_path),
        wait_ms_before_async=2000,
        run_persistent=True,
    )
    assert res1["is_async"] is False
    terminal_id = res1.get("terminal_id")
    assert terminal_id is not None

    # Second invocation referencing the same terminal ID
    res2 = await manager.run_command(
        "echo \"VAL=$ATBMIND_TEST_VAR\"",
        cwd=str(tmp_path),
        wait_ms_before_async=2000,
        requested_terminal_id=terminal_id,
    )
    assert res2["is_async"] is False
    assert "VAL=alpha_beta" in res2["output"]

    await manager.shutdown()


def test_cron_expression_parsing():
    # Test field parsing
    minutes = parse_cron_field("*/15", 0, 59)
    assert minutes == {0, 15, 30, 45}

    hours = parse_cron_field("1,3-5", 0, 23)
    assert hours == {1, 3, 4, 5}

    # Test cron_match
    dt = datetime(2026, 10, 7, 14, 30, 0)
    assert cron_match("30 14 * * *", dt) is True
    assert cron_match("0 14 * * *", dt) is False

    # Test get_next_cron_run
    base = datetime(2026, 10, 7, 14, 0, 0)
    next_run = get_next_cron_run("15 14 * * *", base_time=base)
    assert next_run == datetime(2026, 10, 7, 14, 15, 0)


@pytest.mark.asyncio
async def test_cron_scheduling_and_cancellation():
    bus = AsyncEventBus()
    fired = []
    bus.subscribe(TimerFiredEvent, lambda e: fired.append(e))
    manager = TaskManager(event_bus=bus)

    # Schedule cron
    cron_id = await manager.schedule_cron("Health check", cron_expr="* * * * *", max_iterations=2)
    assert cron_id.startswith("cron-")

    status = manager.get_timer_status(cron_id)
    assert status["is_cron"] is True
    assert status["status"] == "running"

    # Cancel cron
    cancel_res = await manager.manage_task(action="kill", task_id=cron_id)
    assert cancel_res["success"] is True

    status_after = manager.get_timer_status(cron_id)
    assert status_after["status"] in ("cancelled", "killed")

    await manager.shutdown()


@pytest.mark.asyncio
async def test_process_group_termination(tmp_path: Path):
    bus = AsyncEventBus()
    manager = TaskManager(event_bus=bus, log_dir=tmp_path)

    # Launch a process with a child subprocess
    cmd = "sh -c 'sleep 30 & wait'"
    res = await manager.run_command(cmd, cwd=str(tmp_path), wait_ms_before_async=100)
    assert res["is_async"] is True
    task_id = res["task_id"]

    # Kill task
    kill_res = await manager.kill_task(task_id)
    assert kill_res is True

    status = manager.get_task_status(task_id)
    assert status["status"] in (TaskStatus.KILLED.value, TaskStatus.DONE.value)

    await manager.shutdown()
