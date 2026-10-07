# ATBMind Antigravity-Grade 运行时与系统原子工具集设计规范 (Design Spec)

**日期**：2026-10-07  
**状态**：已批准 (Approved)  
**目标**：为 ATBMind 引入类似 Google Antigravity 的高阶智能体能力底座。构建统一异步事件总线（AsyncEventBus）、后台任务与定时调度引擎（TaskManager）、多智能体层级编排与生命周期管理（SubagentOrchestrator），以及工业级系统原子工具包（精细文件操作、持久终端、后台任务交互与提问模态），并无缝打通 PySide6 桌面端事件中继。

---

## 1. 背景与设计目标

### 1.1 现状与痛点
1. **单轮同步委派局限**：目前系统的子智能体委派（`delegate_task`）采用简单同步阻塞方式运行，无法支持多个 Subagent 并发协同、点对点双向通信（`send_message`）以及长期驻留监控。
2. **缺乏后台长任务与调度引擎**：执行耗时命令或代码运行无异步落盘机制，无持久终端上下文（Persistent Terminals），更不支持周期性 Cron 与延时定时器触发的非轮询唤醒机制（Reactive Wakeup）。
3. **系统工具粗糙单薄**：目前的代码操作工具缺乏局部精确搜索替换（`replace_file_content`）与切片分页（`view_file`），智能体全量重写长文件极易产生幻觉与代码截断。
4. **缺少人机协同关键确认流**：复杂架构与破坏性变更缺乏类似于 `ask_question` 的阻断式交互确认模态。

### 1.2 核心目标
1. **统一异步事件总线 (AsyncEventBus)**：建立强类型事件契约，彻底告别 `while True: sleep()` 轮询，支持后台完成即刻自动投递 `<SYSTEM_MESSAGE>` 唤醒。
2. **后台任务与持久终端 (TaskManager)**：支持毫秒级快命令同步返回、长命令平滑转入后台流式落盘、持久终端环境变量保留与 `manage_task` 交互。
3. **多智能体编排与角色深度融合 (SubagentOrchestrator)**：与已有 `RobotRole`（如 `draw_expert`）深度打通，扩展支持 `self` 分身、`research` 探针与 `define_subagent` 动态角色，上下文严格隔离与双向信箱通信。
4. **Antigravity 级系统原子工具集 (Core Toolkits)**：标准化实现精细文件查看/写入/局部精确替换工具包、终端与任务管理包、调度工具包及人机交互提问包。
5. **PySide6 桌面端无缝事件中继**：通过 `GenerationWorker` 将底层异步事件无缝映射为 Qt 信号，驱动桌面端实时展示任务状态、子智能体执行进度与弹窗交互。

---

## 2. 总体架构与系统分层

```
                                ┌──────────────────────────────────────┐
                                │      PySide6 Desktop Application      │
                                │  (ChatStreamView / Sidebar / Modals) │
                                └──────────────────┬───────────────────┘
                                                   │ Qt Signals (Queued)
                                                   ▼
                                ┌──────────────────────────────────────┐
                                │   GenerationWorker (AsyncIO Bridge)  │
                                └──────────────────┬───────────────────┘
                                                   │
                ┌──────────────────────────────────┴──────────────────────────────────┐
                ▼                                                                     ▼
┌───────────────────────────────┐                                   ┌───────────────────────────────────┐
│     Harness Loop (微内核)      │                                   │       AsyncEventBus (事件总线)     │
│   - loop.py (双循环状态机)     │◄──────── 异步唤醒 (Reactive Wakeup) ──────┤   - 强类型 RuntimeEvent 派发与订阅  │
│   - session.py (上下文容器)    │                                   │   - 任务增量日志 / 状态变更广播    │
└───────────────┬───────────────┘                                   └─────────────────▲─────────────────┘
                │ 驱动工具调用                                                          │ 事件冒泡 (Bubbling)
                ▼                                                                     │
┌─────────────────────────────────────────────────────────────────────────────────────┼─────────────────┐
│                                       Runtime Layer (运行时编排层)                   │                 │
│                                                                                     │                 │
│   ┌──────────────────────────────────────────────┐   ┌──────────────────────────────┴─────────────┐   │
│   │        SubagentOrchestrator (多智能体编排)    │   │             TaskManager (任务与调度)       │   │
│   │   - 继承/复用 roles/ RobotRole 预定义蓝图     │   │   - run_command (同步等待/超时转后台)       │   │
│   │   - self 分身 / research 探针 / 动态角色     │   │   - Persistent Terminals (持久终端会话池)   │   │
│   │   - 独立 Session 上下文与双向通信 Mailbox    │   │   - manage_task (状态/日志/标准输入/Kill)    │   │
│   │   - 协程生命周期树 (running/idle/errored)    │   │   - Scheduler (Timer / Cron 周期唤醒)       │   │
│   └──────────────────────┬───────────────────────┘   └──────────────────────────────┬─────────────┘   │
│                          │                                                          │                 │
│                          └───────────────────────────┬──────────────────────────────┘                 │
│                                                      ▼                                                │
│                                       Antigravity Core Toolkits                                       │
│    fs_tools (view/write/replace) │ shell_tools (run/manage) │ schedule_tools │ subagent_tools │ ask_q │
└───────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 详细设计与数据模型

### 3.1 统一异步事件总线 (`atbmind_core/runtime/event_bus.py`)

#### A. 核心事件类型契约
```python
from datetime import datetime
from typing import Any, Callable, Coroutine, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

class RuntimeEvent(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.now)
    source_id: str

class TaskOutputEvent(RuntimeEvent):
    chunk: str
    stream: Literal["stdout", "stderr"] = "stdout"

class TaskStatusChangedEvent(RuntimeEvent):
    old_status: str
    new_status: str  # "RUNNING", "DONE", "FAILED", "KILLED"
    exit_code: Optional[int] = None
    summary: str = ""

class TimerFiredEvent(RuntimeEvent):
    timer_id: str
    prompt: str
    is_cron: bool = False

class SubagentLifecycleEvent(RuntimeEvent):
    subagent_id: str
    state: Literal["running", "idle", "waiting_for_message", "waiting_for_input", "canceling", "errored", "done"]
    detail: str = ""

class SubagentMessageEvent(RuntimeEvent):
    sender_id: str
    recipient_id: str
    content: str
```

#### B. 事件总线实现机制
- `publish(event: RuntimeEvent) -> None`：异步广播给所有匹配该事件类型的订阅回调；
- `subscribe(event_cls, handler: Callable[[T], Coroutine]) -> None`：注册监听；
- 维护一个环形消息队列，支持历史日志安全回放。

---

### 3.2 后台任务与调度引擎 (`atbmind_core/runtime/tasks.py`)

#### A. 后台任务模型
```python
from enum import Enum
import asyncio
from pathlib import Path

class TaskStatus(str, Enum):
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    KILLED = "killed"

class BackgroundTask:
    task_id: str
    command: str
    cwd: str
    status: TaskStatus
    process: Optional[asyncio.subprocess.Process]
    log_file: Path
    exit_code: Optional[int]
    created_at: datetime
```

#### B. 执行与转切逻辑 (`run_command`)
1. **窗口期判定**：智能体传入 `WaitMsBeforeAsync`（默认 5000ms）。
2. 子进程通过 `asyncio.create_subprocess_shell` 启动，标准输出与标准错误自动管道重定向至 `data/tasks/<task_id>.log`。
3. `asyncio.wait_for(process.wait(), timeout=WaitMsBeforeAsync / 1000)`：
   - 若在超时前退出：立即读取末尾输出并同步返回文本内容；
   - 若超时仍未退出：任务平滑保持运行，直接向智能体返回 `task_id`、当前状态和日志路径提示。
4. **持久终端池 (Persistent Terminal Pool)**：
   - 依据 `RequestedTerminalID` 绑定专属 bash 会话；
   - 执行前后注入标记行，共享环境变量并在退出前保持进程常驻。

#### C. 定时与 Cron 调度 (`Scheduler`)
1. **单次定时器**：
   - 记录 `DurationSeconds`、`TimerCondition` 与唤醒 `Prompt`；
   - 监听事件总线，若收到匹配的 `TimerCondition`（如对应任务提前结束），自动静默撤销计时器；
   - 到期未撤销则触发 `TimerFiredEvent`。
2. **周期性 Cron**：
   - 解析 5 段式标准 Cron 表达式计算下一次运行时间点；
   - 支持 `MaxIterations` 迭代次数控制与手动终止。

---

### 3.3 多智能体编排与角色深度融合 (`atbmind_core/runtime/subagents.py`)

#### A. 角色解析矩阵
- **预定义角色 (`TypeName="draw_expert"` 等)**：直接读取 `roles/<role_id>/role.yaml`，加载其 `system_prompt`、模型参数配置与挂载技能（如 `image_generation`）；
- **通用分身 (`TypeName="self"`)**：克隆父智能体的全部配置（包含系统提示词与当前可用工具集）；
- **只读研究员 (`TypeName="research"`)**：内置专注安全探索的只读提示词，仅挂载 `view_file`、`search_web`、`read_url_content` 等无害工具；
- **临机定义角色 (`define_subagent`)**：在内存中注册动态角色元数据，供后续 `invoke_subagent` 多次调用。

#### B. 运行时拓扑与信箱 (Mailbox)
- 每个 Subagent 独立跑在后台协程中，持有独立的 `AgentSession`；
- **点对点通信**：`send_message(recipient, message)` 将消息推入目标智能体的消息信箱并将其从 `waiting_for_message` 状态唤醒；
- **防污染汇总结算**：Subagent 执行完毕时，仅返回最终的输出摘要与产物链接，其庞大的上下文与重试历史自动写入 `data/subagents/<subagent_id>.jsonl`，不累加至父对话 Token 账本。

---

### 3.4 Antigravity 核心系统工具集 (`atbmind_core/runtime/tools/`)

#### 1. 文件系统三剑客 (`fs_tools.py`)
- **`ViewFileTool` (`view_file`)**：
  - 参数：`AbsolutePath: str`, `StartLine: Optional[int]`, `EndLine: Optional[int]`, `ContentOffset: Optional[int]`；
  - 严格限制单次返回不超过 800 行与 45KB，输出自动携带 `1: <代码内容>` 统一行号；
  - 二进制格式感知（图片、PDF、音视频提示类型与文件大小，禁止乱码输出）。
- **`ReplaceFileContentTool` (`replace_file_content`)**：
  - 参数：`TargetFile: str`, `Instruction: str`, `Description: str`, `StartLine: int`, `EndLine: int`, `TargetContent: str`, `ReplacementContent: str`, `AllowMultiple: bool = False`；
  - 在 `[StartLine, EndLine]` 行号范围内严格搜索 `TargetContent`；
  - 校验匹配次数：为 0 或大于 1（且 `AllowMultiple=False`）时返回精确错误与上下文定位，只有唯一匹配时才执行原子替换。
- **`WriteToFileTool` (`write_to_file`)**：
  - 参数：`TargetFile: str`, `CodeContent: str`, `Overwrite: bool`, `Append: bool`, `Description: str`, `ArtifactMetadata: Optional[dict]`；
  - 自动递归创建上层目录；根据开关安全覆盖或追加。

#### 2. 命令行与任务两件套 (`shell_tools.py`)
- **`RunCommandTool` (`run_command`)**：
  - 参数：`CommandLine: str`, `Cwd: str`, `WaitMsBeforeAsync: int = 5000`, `IsDaemon: bool = False`, `RunPersistent: bool = False`, `RequestedTerminalID: Optional[str] = None`；
  - 对接 `TaskManager` 执行。
- **`ManageTaskTool` (`manage_task`)**：
  - 参数：`Action: Literal["list", "kill", "status", "send_input"]`, `TaskId: Optional[str]`, `Input: Optional[str]`。

#### 3. 调度工具 (`schedule_tools.py`)
- **`ScheduleTool` (`schedule`)**：
  - 参数：`Prompt: str`, `DurationSeconds: Optional[int]`, `CronExpression: Optional[str]`, `TimerCondition: Optional[str] = "never"`, `MaxIterations: Optional[int] = None`, `IsDaemon: bool = False`。

#### 4. 多智能体协作工具 (`subagent_tools.py`)
- **`InvokeSubagentTool` (`invoke_subagent`)**：批量分发子智能体任务列表；
- **`SendMessageTool` (`send_message`)**：点对点信箱通信；
- **`ManageSubagentsTool` (`manage_subagents`)**：列出活跃智能体列表、查看状态或杀死任务；
- **`DefineSubagentTool` (`define_subagent`)**：临机注册新角色能力。

#### 5. 交互式确认模态 (`interaction_tools.py`)
- **`AskQuestionTool` (`ask_question`)**：
  - 参数：`questions: List[dict]`（支持选项、推荐项与多选控制）；
  - 调用时挂起执行，向桌面端派发确认事件，等待主线程 Future 兑现后注入回答。

---

### 3.5 桌面端集成与 Qt 信号桥接 (`apps/atbmind_desktop/workers.py`)

- **`GenerationWorker` 升级**：
  - 在工作线程中创建专属 `asyncio` 事件循环；
  - 订阅 `AsyncEventBus` 关键事件并中继发射 Qt 线程安全信号：
    - `sig_subagent_state = Signal(str, str, str)`（子智能体 ID、状态、详细描述）
    - `sig_task_output = Signal(str, str)`（任务 ID、日志片段）
    - `sig_task_completed = Signal(str, int, str)`（任务 ID、退出码、总结）
    - `sig_ask_question = Signal(object, object)`（问题字典、`asyncio.Future` 对象）
  - 支持 `stop()` 级联杀死异步取消令牌与系统子进程。

---

## 4. 目录结构变更清单

```text
ATBMind/
├── atbmind_core/
│   ├── runtime/                               # [NEW] Antigravity 核心运行时
│   │   ├── __init__.py
│   │   ├── event_bus.py                       # 异步事件总线与事件定义
│   │   ├── tasks.py                           # 任务管理器、持久终端与调度器
│   │   ├── subagents.py                       # 多智能体编排器与生命周期树
│   │   └── tools/                             # 核心系统原子工具集
│   │       ├── __init__.py
│   │       ├── fs_tools.py                    # view_file, write_to_file, replace_file_content
│   │       ├── shell_tools.py                 # run_command, manage_task
│   │       ├── schedule_tools.py              # schedule
│   │       ├── subagent_tools.py              # invoke_subagent, send_message, manage_subagents, define_subagent
│   │       └── interaction_tools.py           # ask_question
├── apps/
│   └── atbmind_desktop/
│       └── workers.py                         # [UPDATE] 升级 GenerationWorker 支持异步总线与 Qt 信号桥接
└── tests/                                     # [NEW] 自动化测试套件
    ├── test_runtime_event_bus.py              # 事件总线订阅/广播测试
    ├── test_runtime_tasks.py                  # 快慢命令、持久终端与调度测试
    ├── test_runtime_tools_fs.py               # 文件精准查看与替换测试
    ├── test_runtime_subagents.py              # 子智能体生命周期与隔离测试
    └── test_runtime_desktop_bridge.py         # Qt 信号中继与取消测试
```

---

## 5. 测试与验证策略

采用严格的 TDD（测试驱动开发）流程，执行全套单测与集成测试：
1. **测试基线**：确保现有全部 182 项测试不受破坏；
2. **测试用例集**：
   - `test_runtime_event_bus.py`：验证异步广播、多协程无阻塞消费、强类型数据契约；
   - `test_runtime_tasks.py`：验证快命令（<100ms）同步返回输出、慢命令（长挂起）自动切后台返回 TaskId、`manage_task(kill)` 正常终止进程、Timer 提前取消条件生效；
   - `test_runtime_tools_fs.py`：验证 `view_file` 行号范围切片与截断、`replace_file_content` 唯一匹配替换成功、多匹配与未匹配精细报错、`write_to_file` 目录自建；
   - `test_runtime_subagents.py`：验证 `draw_expert` 预定义角色加载、`self` 分身继承、`research` 只读限制、子会话上下文隔离验证；
   - `test_runtime_desktop_bridge.py`：利用 `pytest-qt` 验证 `GenerationWorker` 信号中继。
3. **全流程回归**：执行 `PYTHONPATH=src:apps:. conda run -n ATBMind python -m pytest tests/`，必须达到 100% 通过率。
