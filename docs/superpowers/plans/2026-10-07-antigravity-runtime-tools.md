# Antigravity 运行时与系统原子工具集 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 ATBMind 构建具备 Antigravity 能力特性的系统底座，包括统一异步事件总线、后台命令与持久终端调度器、多智能体层级编排生命周期，以及工业级系统原子工具包（精细文件操作、任务管理、定时唤醒与交互提问模态），并打通 PySide6 桌面端信号桥接。

**Architecture:** 基于 Python 3.12 原生 `asyncio` 协程与子进程，解耦出 `runtime/` 核心层。通过 `AsyncEventBus` 驱动任务完成与定时的非轮询式主动唤醒（Reactive Wakeup），由 `TaskManager` 统一治理 Shell 快慢命令与持久终端，由 `SubagentOrchestrator` 深度融合现有 `RobotRole` 并提供上下文隔离的子智能体树，通过 `GenerationWorker` 将底层异步事件中继映射为 PySide6 线程安全 Qt 信号。

**Tech Stack:** Python 3.12+, `asyncio`, `asyncio.subprocess`, Pydantic v2, PySide6, pytest, pytest-qt, pytest-asyncio

**Spec:** [docs/superpowers/specs/2026-10-07-antigravity-runtime-tools-design.md](file:///Users/brainzhang/work/aitobox/ATBMind/docs/superpowers/specs/2026-10-07-antigravity-runtime-tools-design.md)

## Global Constraints

- 运行环境必须为 Conda `ATBMind` (`python 3.12+`)，所有测试命令使用 `PYTHONPATH=src:apps:. conda run -n ATBMind python -m pytest tests/`
- 所有工具类必须继承 `atbmind_core.harness.tools.base.AgentTool` 并使用 Pydantic BaseModel 进行参数强类型校验
- 不引入重型外部队列与服务端框架（Zero Heavy Dependencies），保持纯原生标准库与极简架构
- 现有 182 项测试必须保持 100% 通过，无回归破坏

## Review Focus

1. **子进程僵尸与进程组泄漏**：长时间后台命令被杀死或桌面端意外停止时，必须通过 `os.killpg` 发送 `SIGTERM`/`SIGKILL` 级联终止整棵子进程树，防止后台残留孤儿进程。
2. **文件精细替换（`replace_file_content`）搜索区间歧义**：当 `TargetContent` 在 `[StartLine, EndLine]` 搜索窗口中出现 0 次或超过 1 次时，不能静默失败或错位替换，必须返回明确的定位诊断信息。
3. **超长文件与二进制文件读取防爆**：`view_file` 必须自动拦截图片、音视频等二进制文件并提示格式信息；读取超长文本时必须受 800 行与 45KB 截断保护，支持 `ContentOffset`。
4. **子智能体（Subagent）上下文防污染**：子智能体的内部中间推理（Thinking）、工具重试信息必须保留在子会话中，写入独立 JSONL 日志，绝不可泄漏并污染主会话的 Token 窗口。
5. **跨线程 Qt 信号安全性**：在后台线程中运行的 asyncio 协程向 PySide6 发送信号时，必须通过 Qt 自带的 `QueuedConnection` 机制传递拷贝数据，禁止跨线程直接操作 UI 控件。

---

### Task 1: 统一异步事件总线 (AsyncEventBus)

**Files:**
- Create: `atbmind_core/runtime/__init__.py`
- Create: `atbmind_core/runtime/event_bus.py`
- Test: `tests/test_runtime_event_bus.py`

**Interfaces:**
- Consumes: `pydantic.BaseModel`
- Produces: `RuntimeEvent`, `TaskOutputEvent`, `TaskStatusChangedEvent`, `TimerFiredEvent`, `SubagentLifecycleEvent`, `SubagentMessageEvent`, `AsyncEventBus` (`publish(event)`, `subscribe(event_cls, handler)`, `get_history(limit)`)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_runtime_event_bus.py
import pytest
import asyncio
from atbmind_core.runtime.event_bus import (
    AsyncEventBus,
    RuntimeEvent,
    TaskOutputEvent,
    TaskStatusChangedEvent,
    TimerFiredEvent,
    SubagentLifecycleEvent,
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src:apps:. conda run -n ATBMind python -m pytest tests/test_runtime_event_bus.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'atbmind_core.runtime'`

- [ ] **Step 3: Implement `atbmind_core/runtime/event_bus.py`**

实现强类型事件模型与 `AsyncEventBus` 类，支持基于类型过滤的订阅者列表分发，采用环形 deque 缓存历史事件。

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src:apps:. conda run -n ATBMind python -m pytest tests/test_runtime_event_bus.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add atbmind_core/runtime/ tests/test_runtime_event_bus.py
git commit -m "feat(runtime): add AsyncEventBus with typed runtime events"
```

---

### Task 2: 后台任务、持久终端与调度引擎 (TaskManager)

**Files:**
- Create: `atbmind_core/runtime/tasks.py`
- Test: `tests/test_runtime_tasks.py`

**Interfaces:**
- Consumes: `AsyncEventBus`, `TaskOutputEvent`, `TaskStatusChangedEvent`, `TimerFiredEvent`
- Produces: `TaskManager` (`run_command(cmd, cwd, wait_ms, persistent_id, is_daemon)`, `manage_task(action, task_id, input_text)`, `schedule_timer(prompt, duration_s, condition)`, `schedule_cron(prompt, cron_expr, max_iterations)`)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_runtime_tasks.py
import pytest
import asyncio
from pathlib import Path
from atbmind_core.runtime.event_bus import AsyncEventBus
from atbmind_core.runtime.tasks import TaskManager, TaskStatus

@pytest.mark.asyncio
async def test_fast_command_runs_synchronously(tmp_path: Path):
    bus = AsyncEventBus()
    manager = TaskManager(event_bus=bus, log_dir=tmp_path)
    result = await manager.run_command("echo 'sync test'", cwd=str(tmp_path), wait_ms_before_async=2000)
    assert result["is_async"] is False
    assert "sync test" in result["output"]

@pytest.mark.asyncio
async def test_slow_command_transitions_to_background_and_kill(tmp_path: Path):
    bus = AsyncEventBus()
    manager = TaskManager(event_bus=bus, log_dir=tmp_path)
    # 慢命令：sleep 10
    result = await manager.run_command("sleep 10", cwd=str(tmp_path), wait_ms_before_async=200)
    assert result["is_async"] is True
    task_id = result["task_id"]
    status_info = manager.get_task_status(task_id)
    assert status_info["status"] == TaskStatus.RUNNING.value

    # 终止任务
    kill_res = await manager.kill_task(task_id)
    assert kill_res is True
    await asyncio.sleep(0.1)
    status_after = manager.get_task_status(task_id)
    assert status_after["status"] in (TaskStatus.KILLED.value, TaskStatus.DONE.value)

@pytest.mark.asyncio
async def test_scheduler_one_shot_timer():
    bus = AsyncEventBus()
    fired = []
    bus.subscribe(TimerFiredEvent, lambda e: fired.append(e.prompt))
    manager = TaskManager(event_bus=bus)
    timer_id = await manager.schedule_timer("Wakeup alert", duration_s=0.1)
    await asyncio.sleep(0.2)
    assert len(fired) == 1
    assert fired[0] == "Wakeup alert"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src:apps:. conda run -n ATBMind python -m pytest tests/test_runtime_tasks.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'atbmind_core.runtime.tasks'`

- [ ] **Step 3: Implement `atbmind_core/runtime/tasks.py`**

实现 `TaskManager`：
1. `run_command`：通过 `asyncio.create_subprocess_shell(..., preexec_fn=os.setsid)` 创建子进程，并管道输出至文件；用 `asyncio.wait_for` 判断是否超时；超时返回 task_id；
2. `kill_task`：`os.killpg(os.getpgid(proc.pid), signal.SIGTERM)` 优雅清理进程组；
3. `manage_task`：提供状态查询、stdin 写入与列表列出；
4. `schedule_timer` 与 `schedule_cron`：调度器管理与定时触发。

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src:apps:. conda run -n ATBMind python -m pytest tests/test_runtime_tasks.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add atbmind_core/runtime/tasks.py tests/test_runtime_tasks.py
git commit -m "feat(runtime): add TaskManager for background shell execution and scheduling"
```

---

### Task 3: 精细化文件系统原子工具集 (fs_tools.py)

**Files:**
- Create: `atbmind_core/runtime/tools/__init__.py`
- Create: `atbmind_core/runtime/tools/fs_tools.py`
- Test: `tests/test_runtime_tools_fs.py`

**Interfaces:**
- Consumes: `atbmind_core.harness.tools.base.AgentTool`
- Produces: `ViewFileTool`, `WriteToFileTool`, `ReplaceFileContentTool`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_runtime_tools_fs.py
import pytest
from pathlib import Path
from atbmind_core.runtime.tools.fs_tools import ViewFileTool, WriteToFileTool, ReplaceFileContentTool

def test_view_file_slice_and_numbering(tmp_path: Path):
    f = tmp_path / "sample.txt"
    f.write_text("line1\nline2\nline3\nline4\nline5\n")
    tool = ViewFileTool()
    res = tool.execute(AbsolutePath=str(f), StartLine=2, EndLine=4)
    assert res.success is True
    assert "2: line2" in res.output
    assert "3: line3" in res.output
    assert "4: line4" in res.output
    assert "1: line1" not in res.output

def test_replace_file_content_exact_match(tmp_path: Path):
    f = tmp_path / "code.py"
    f.write_text("def hello():\n    return 42\n")
    tool = ReplaceFileContentTool()
    res = tool.execute(
        TargetFile=str(f),
        StartLine=1,
        EndLine=2,
        TargetContent="    return 42",
        ReplacementContent="    return 100",
        Instruction="update return value",
        Description="change 42 to 100"
    )
    assert res.success is True
    assert f.read_text() == "def hello():\n    return 100\n"

def test_replace_file_content_error_on_mismatch(tmp_path: Path):
    f = tmp_path / "code.py"
    f.write_text("def hello():\n    return 42\n")
    tool = ReplaceFileContentTool()
    res = tool.execute(
        TargetFile=str(f),
        StartLine=1,
        EndLine=2,
        TargetContent="    return 999",
        ReplacementContent="    return 100",
        Instruction="bad replace",
        Description="test"
    )
    assert res.success is False
    assert "not found" in res.error.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src:apps:. conda run -n ATBMind python -m pytest tests/test_runtime_tools_fs.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'atbmind_core.runtime.tools'`

- [ ] **Step 3: Implement `atbmind_core/runtime/tools/fs_tools.py`**

实现 `ViewFileTool`、`WriteToFileTool`、`ReplaceFileContentTool`，遵循 Antigravity 参数和行号、截断与匹配规范。

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src:apps:. conda run -n ATBMind python -m pytest tests/test_runtime_tools_fs.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add atbmind_core/runtime/tools/fs_tools.py tests/test_runtime_tools_fs.py
git commit -m "feat(runtime): add Antigravity-grade fs tools view_file, write_to_file, replace_file_content"
```

---

### Task 4: 终端命令、任务治理与调度工具集 (shell_tools.py & schedule_tools.py)

**Files:**
- Create: `atbmind_core/runtime/tools/shell_tools.py`
- Create: `atbmind_core/runtime/tools/schedule_tools.py`
- Test: `tests/test_runtime_tools_shell_and_schedule.py`

**Interfaces:**
- Consumes: `TaskManager`, `atbmind_core.harness.tools.base.AgentTool`
- Produces: `RunCommandTool`, `ManageTaskTool`, `ScheduleTool`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_runtime_tools_shell_and_schedule.py
import pytest
from pathlib import Path
from atbmind_core.runtime.event_bus import AsyncEventBus
from atbmind_core.runtime.tasks import TaskManager
from atbmind_core.runtime.tools.shell_tools import RunCommandTool, ManageTaskTool
from atbmind_core.runtime.tools.schedule_tools import ScheduleTool

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

@pytest.mark.asyncio
async def test_schedule_tool():
    bus = AsyncEventBus()
    tm = TaskManager(event_bus=bus)
    sched_tool = ScheduleTool(task_manager=tm)
    res = await sched_tool.execute_async(Prompt="Do periodic check", DurationSeconds=60, TimerCondition="never")
    assert res.success is True
    assert "timer-" in res.output or "scheduled" in res.output.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src:apps:. conda run -n ATBMind python -m pytest tests/test_runtime_tools_shell_and_schedule.py -v`  
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `shell_tools.py` & `schedule_tools.py`**

封装 `RunCommandTool`、`ManageTaskTool` 与 `ScheduleTool`，对齐 Antigravity 标准参数结构。

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src:apps:. conda run -n ATBMind python -m pytest tests/test_runtime_tools_shell_and_schedule.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add atbmind_core/runtime/tools/shell_tools.py atbmind_core/runtime/tools/schedule_tools.py tests/test_runtime_tools_shell_and_schedule.py
git commit -m "feat(runtime): add run_command, manage_task, and schedule tools"
```

---

### Task 5: 多智能体编排器与生命周期协同 (SubagentOrchestrator & subagent_tools.py)

**Files:**
- Create: `atbmind_core/runtime/subagents.py`
- Create: `atbmind_core/runtime/tools/subagent_tools.py`
- Test: `tests/test_runtime_subagents.py`

**Interfaces:**
- Consumes: `RobotRoleRegistry`, `AsyncEventBus`, `AgentSession`
- Produces: `SubagentOrchestrator`, `InvokeSubagentTool`, `SendMessageTool`, `ManageSubagentsTool`, `DefineSubagentTool`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_runtime_subagents.py
import pytest
from pathlib import Path
from atbmind_core.runtime.event_bus import AsyncEventBus
from atbmind_core.runtime.subagents import SubagentOrchestrator, SubagentState
from atbmind_core.roles.registry import RobotRoleRegistry
from atbmind_core.runtime.tools.subagent_tools import InvokeSubagentTool, ManageSubagentsTool, SendMessageTool

@pytest.mark.asyncio
async def test_subagent_orchestration_flow(tmp_path: Path):
    bus = AsyncEventBus()
    role_registry = RobotRoleRegistry()
    role_registry.scan("roles") # 加载已有的 draw_expert, coordinator
    orchestrator = SubagentOrchestrator(event_bus=bus, role_registry=role_registry, transcript_dir=tmp_path)

    # 1. 派发已有的 draw_expert
    sub_id = await orchestrator.spawn_subagent(
        type_name="draw_expert",
        role_title="Visual Specialist",
        prompt="Draw a cyberpunk cat",
        parent_id="root-session"
    )
    assert sub_id is not None
    info = orchestrator.get_subagent_info(sub_id)
    assert info["type"] == "draw_expert"
    assert info["state"] in [SubagentState.RUNNING.value, SubagentState.IDLE.value]

    # 2. 发送消息
    msg_res = await orchestrator.send_message(recipient_id=sub_id, message="Please add neon lights", sender_id="root-session")
    assert msg_res is True

    # 3. 列出
    subagents = orchestrator.list_subagents()
    assert len(subagents) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src:apps:. conda run -n ATBMind python -m pytest tests/test_runtime_subagents.py -v`  
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `subagents.py` & `subagent_tools.py`**

1. `SubagentOrchestrator`：维护子智能体状态机，支持 `draw_expert`（读取已有 YAML）、`self`（继承父 Prompt）、`research` 与动态角色，写入独立日志 `transcript_dir/<id>.jsonl`；
2. 实现 `InvokeSubagentTool`、`SendMessageTool`、`ManageSubagentsTool` 与 `DefineSubagentTool`。

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src:apps:. conda run -n ATBMind python -m pytest tests/test_runtime_subagents.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add atbmind_core/runtime/subagents.py atbmind_core/runtime/tools/subagent_tools.py tests/test_runtime_subagents.py
git commit -m "feat(runtime): add SubagentOrchestrator and subagent tools"
```

---

### Task 6: 交互式提问模态与 PySide6 桌面端信号桥接 (Interaction & Desktop Bridge)

**Files:**
- Create: `atbmind_core/runtime/tools/interaction_tools.py`
- Modify: `apps/atbmind_desktop/workers.py`
- Test: `tests/test_runtime_desktop_bridge.py`

**Interfaces:**
- Consumes: `AsyncEventBus`, `AskQuestionTool`, `PySide6.QtCore.QThread`, `PySide6.QtCore.Signal`
- Produces: `AskQuestionTool`, `GenerationWorker` (with `sig_subagent_state`, `sig_task_output`, `sig_task_completed`, `sig_ask_question`)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_runtime_desktop_bridge.py
import pytest
import asyncio
from pytestqt.qtbot import QtBot
from apps.atbmind_desktop.workers import GenerationWorker
from atbmind_core.runtime.event_bus import AsyncEventBus, TaskOutputEvent, SubagentLifecycleEvent

def test_generation_worker_bridges_runtime_events(qtbot: QtBot):
    worker = GenerationWorker(session_id="test-session", user_input="hello")
    subagent_states = []
    worker.sig_subagent_state.connect(lambda s_id, st, det: subagent_states.append((s_id, st)))

    # 测试桥接发射
    worker.bridge_subagent_event(SubagentLifecycleEvent(source_id="sub-1", subagent_id="sub-1", state="running", detail="working"))
    assert len(subagent_states) == 1
    assert subagent_states[0] == ("sub-1", "running")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src:apps:. conda run -n ATBMind python -m pytest tests/test_runtime_desktop_bridge.py -v`  
Expected: FAIL with AttributeError or missing method

- [ ] **Step 3: Implement `interaction_tools.py` and update `workers.py`**

1. `AskQuestionTool`：向事件总线派发 `AskQuestionEvent`，异步等待返回答案；
2. 扩展 `GenerationWorker`：新增 `sig_subagent_state`、`sig_task_output`、`sig_task_completed`、`sig_ask_question` 信号，并在其事件循环中绑定 `AsyncEventBus` 监听。

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src:apps:. conda run -n ATBMind python -m pytest tests/test_runtime_desktop_bridge.py -v`  
Expected: PASS

- [ ] **Step 5: Run full project test suite**

Run: `PYTHONPATH=src:apps:. conda run -n ATBMind python -m pytest tests/`  
Expected: All 182+ tests pass (100% green).

- [ ] **Step 6: Commit**

```bash
git add atbmind_core/runtime/tools/interaction_tools.py apps/atbmind_desktop/workers.py tests/test_runtime_desktop_bridge.py
git commit -m "feat(runtime): add ask_question tool and upgrade GenerationWorker with Qt signal bridge"
```
