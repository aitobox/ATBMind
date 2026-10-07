import pytest
import asyncio
from atbmind_core.runtime.event_bus import (
    AsyncEventBus,
    RuntimeEvent,
    TaskOutputEvent,
    TaskStatusChangedEvent,
    TimerFiredEvent,
    SubagentLifecycleEvent,
    SubagentMessageEvent,
)

@pytest.mark.asyncio
async def test_event_bus_publish_and_subscribe():
    bus = AsyncEventBus()
    received_outputs = []

    async def on_output(event: TaskOutputEvent):
        received_outputs.append(event.chunk)

    bus.subscribe(TaskOutputEvent, on_output)
    await bus.publish(TaskOutputEvent(source_id="task-1", chunk="hello world"))

    assert len(received_outputs) == 1
    assert received_outputs[0] == "hello world"

@pytest.mark.asyncio
async def test_event_bus_history_and_filtering():
    bus = AsyncEventBus(max_history=10)
    await bus.publish(TaskStatusChangedEvent(source_id="task-2", old_status="running", new_status="done"))
    history = bus.get_history()
    assert len(history) == 1
    assert history[0].source_id == "task-2"

@pytest.mark.asyncio
async def test_event_bus_sync_and_async_handlers():
    bus = AsyncEventBus()
    sync_called = []
    async_called = []

    def sync_handler(event: RuntimeEvent):
        sync_called.append(event.source_id)

    async def async_handler(event: RuntimeEvent):
        async_called.append(event.source_id)

    bus.subscribe(RuntimeEvent, sync_handler)
    bus.subscribe(RuntimeEvent, async_handler)

    await bus.publish(RuntimeEvent(source_id="root-1"))

    assert sync_called == ["root-1"]
    assert async_called == ["root-1"]

@pytest.mark.asyncio
async def test_event_bus_polymorphic_subscription():
    bus = AsyncEventBus()
    all_events = []
    specific_events = []

    bus.subscribe(RuntimeEvent, lambda e: all_events.append(e))
    bus.subscribe(TaskOutputEvent, lambda e: specific_events.append(e))

    await bus.publish(TaskOutputEvent(source_id="task-1", chunk="out"))
    await bus.publish(TaskStatusChangedEvent(source_id="task-1", old_status="running", new_status="done"))

    assert len(all_events) == 2
    assert len(specific_events) == 1
    assert specific_events[0].chunk == "out"

@pytest.mark.asyncio
async def test_event_bus_history_limit_and_filter():
    bus = AsyncEventBus(max_history=5)
    for i in range(10):
        await bus.publish(TaskOutputEvent(source_id=f"task-{i}", chunk=f"chunk-{i}"))

    history = bus.get_history()
    # deque max_history is 5
    assert len(history) == 5
    assert history[0].source_id == "task-5"
    assert history[-1].source_id == "task-9"

    # limit filter
    assert len(bus.get_history(limit=2)) == 2
    assert bus.get_history(limit=2)[-1].source_id == "task-9"

    # event_cls and source_id filter
    await bus.publish(TaskStatusChangedEvent(source_id="task-x", old_status="init", new_status="running"))
    status_events = bus.get_history(event_cls=TaskStatusChangedEvent)
    assert len(status_events) == 1
    assert status_events[0].source_id == "task-x"

    source_events = bus.get_history(source_id="task-x")
    assert len(source_events) == 1

@pytest.mark.asyncio
async def test_event_bus_unsubscribe():
    bus = AsyncEventBus()
    received = []

    def handler(event: TaskOutputEvent):
        received.append(event.chunk)

    bus.subscribe(TaskOutputEvent, handler)
    await bus.publish(TaskOutputEvent(source_id="task-1", chunk="first"))
    assert received == ["first"]

    assert bus.unsubscribe(TaskOutputEvent, handler) is True
    await bus.publish(TaskOutputEvent(source_id="task-1", chunk="second"))
    assert received == ["first"]

@pytest.mark.asyncio
async def test_event_bus_exception_isolation():
    bus = AsyncEventBus()
    success_called = []

    def failing_handler(event: TaskOutputEvent):
        raise RuntimeError("Handler failed!")

    def good_handler(event: TaskOutputEvent):
        success_called.append(event.chunk)

    bus.subscribe(TaskOutputEvent, failing_handler)
    bus.subscribe(TaskOutputEvent, good_handler)

    # Should not raise exception out of publish
    await bus.publish(TaskOutputEvent(source_id="task-1", chunk="hello"))
    assert success_called == ["hello"]

def test_event_models():
    out = TaskOutputEvent(source_id="t1", chunk="abc", stream="stderr")
    assert out.chunk == "abc"
    assert out.stream == "stderr"

    timer = TimerFiredEvent(timer_id="time-1", prompt="wake up")
    assert timer.source_id == "time-1"
    assert timer.prompt == "wake up"

    sub = SubagentLifecycleEvent(subagent_id="sub-1", state="running")
    assert sub.source_id == "sub-1"
    assert sub.state == "running"

    msg = SubagentMessageEvent(sender_id="s1", recipient_id="r1", content="hi")
    assert msg.source_id == "s1"
    assert msg.recipient_id == "r1"
    assert msg.content == "hi"
