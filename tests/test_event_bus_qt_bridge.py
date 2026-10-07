import pytest
from PySide6.QtCore import QCoreApplication
from atbmind_core.runtime.event_bus import (
    AsyncEventBus,
    SubagentLifecycleEvent,
    TaskStatusChangedEvent,
    TimerFiredEvent,
    SkillActivatedEvent,
    FilesChangedEvent,
)
from apps.atbmind_desktop.bridge import EventBusQtBridge


@pytest.mark.asyncio
async def test_event_bus_qt_bridge_signals(qtbot):
    bus = AsyncEventBus()
    bridge = EventBusQtBridge()
    bridge.attach_bus(bus)
    assert bridge.bus is bus

    # SubagentLifecycleEvent
    with qtbot.waitSignal(bridge.subagent_lifecycle_changed, timeout=1000) as subagent_signal:
        await bus.publish(
            SubagentLifecycleEvent(subagent_id="sub-1", state="running", detail="Working on step 1")
        )
    assert subagent_signal.args == ["sub-1", "running", "Working on step 1"]

    # TaskStatusChangedEvent
    with qtbot.waitSignal(bridge.task_status_changed, timeout=1000) as task_signal:
        await bus.publish(
            TaskStatusChangedEvent(source_id="task-1", old_status="pending", new_status="done", summary="Build complete")
        )
    assert task_signal.args == ["task-1", "done", "Build complete"]

    # TimerFiredEvent
    with qtbot.waitSignal(bridge.timer_fired, timeout=1000) as timer_signal:
        await bus.publish(
            TimerFiredEvent(timer_id="timer-1", prompt="Remind user to review PR", is_cron=True)
        )
    assert timer_signal.args == ["timer-1", "Remind user to review PR", True]

    # SkillActivatedEvent
    with qtbot.waitSignal(bridge.skill_activated, timeout=1000) as skill_signal:
        await bus.publish(
            SkillActivatedEvent(skill_name="brainstorming", skill_path="/skills/brainstorming/SKILL.md")
        )
    assert skill_signal.args == ["brainstorming", "/skills/brainstorming/SKILL.md"]

    # FilesChangedEvent
    with qtbot.waitSignal(bridge.files_changed_updated, timeout=1000) as files_signal:
        await bus.publish(
            FilesChangedEvent(files=["apps/atbmind_desktop/bridge.py", "tests/test_event_bus_qt_bridge.py"])
        )
    assert files_signal.args == [["apps/atbmind_desktop/bridge.py", "tests/test_event_bus_qt_bridge.py"]]

    # Test detach_bus stops event propagation to signals
    bridge.detach_bus()
    assert bridge.bus is None
    received_after_detach = []
    bridge.subagent_lifecycle_changed.connect(lambda *args: received_after_detach.append(args))
    await bus.publish(
        SubagentLifecycleEvent(subagent_id="sub-2", state="done", detail="Completed")
    )
    assert received_after_detach == []

    # Calling detach_bus again should be safe and idempotent
    bridge.detach_bus()
    assert bridge.bus is None


@pytest.mark.asyncio
async def test_event_bus_qt_bridge_reattach(qtbot):
    bus1 = AsyncEventBus()
    bus2 = AsyncEventBus()
    bridge = EventBusQtBridge()

    bridge.attach_bus(bus1)
    assert bridge.bus is bus1

    # Re-attach to bus2
    bridge.attach_bus(bus2)
    assert bridge.bus is bus2

    # Events from bus1 should no longer be handled
    received_events = []
    bridge.subagent_lifecycle_changed.connect(lambda *args: received_events.append(args))

    await bus1.publish(
        SubagentLifecycleEvent(subagent_id="sub-old", state="running", detail="Should be ignored")
    )
    assert received_events == []

    # Events from bus2 should be handled
    with qtbot.waitSignal(bridge.subagent_lifecycle_changed, timeout=1000) as sig:
        await bus2.publish(
            SubagentLifecycleEvent(subagent_id="sub-new", state="running", detail="Active")
        )
    assert sig.args == ["sub-new", "running", "Active"]

    bridge.detach_bus()


def test_event_bus_qt_bridge_fallback_direct_emits(qtbot):
    bridge = EventBusQtBridge()
    assert bridge.bus is None

    # Test direct emission helpers without a bus
    with qtbot.waitSignal(bridge.subagent_lifecycle_changed, timeout=1000) as sub_sig:
        bridge.emit_subagent_lifecycle("sub-fallback", "waiting_for_input", "Waiting on user")
    assert sub_sig.args == ["sub-fallback", "waiting_for_input", "Waiting on user"]

    with qtbot.waitSignal(bridge.task_status_changed, timeout=1000) as task_sig:
        bridge.emit_task_status("task-fallback", "failed", "OOM error")
    assert task_sig.args == ["task-fallback", "failed", "OOM error"]

    with qtbot.waitSignal(bridge.timer_fired, timeout=1000) as timer_sig:
        bridge.emit_timer_fired("timer-fallback", "Check health", False)
    assert timer_sig.args == ["timer-fallback", "Check health", False]

    with qtbot.waitSignal(bridge.skill_activated, timeout=1000) as skill_sig:
        bridge.emit_skill_activated("my-skill", "/path/to/my-skill")
    assert skill_sig.args == ["my-skill", "/path/to/my-skill"]

    with qtbot.waitSignal(bridge.files_changed_updated, timeout=1000) as files_sig:
        bridge.emit_files_changed(["file1.txt", "file2.txt"])
    assert files_sig.args == [["file1.txt", "file2.txt"]]

    with qtbot.waitSignal(bridge.queued_message_dispatched, timeout=1000) as queue_sig:
        bridge.emit_queued_message_dispatched("queued prompt")
    assert queue_sig.args == ["queued prompt"]
