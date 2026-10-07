# ATBMind Pi-Style Micro-Harness 架构设计规范

**文档状态**: 草案 / 待评审  
**创建日期**: 2026-10-07  
**参考项目**: [earendil-works/pi](https://github.com/earendil-works/pi)  
**目标系统**: ATBMind 核心执行引擎与桌面端 (`atbmind_core`, `apps/atbmind_desktop`)

---

## 1. 背景与目标 (Context & Objectives)

### 1.1 现状与痛点
ATBMind 目前采用静态的三层意图推理引擎（Layer 1 意图补全 `Completer` -> Layer 2 拓扑规划 `Planner` -> Layer 3 槽位调度 `Dispatcher`）。该结构在处理单次结构化任务时具备一定确定性，但存在以下硬伤：
1. **黑盒阻塞**：无法实现精细的打字机 Token 级流式输出与运行中进度展示。
2. **缺乏自纠错机制**：如果底层工具报错或参数不合法，整体管道直接崩溃，模型无法基于错误信息自我修正。
3. **无法中途交互（No Steering）**：任务一旦启动，用户无法在执行循环中注入补充指令或及时纠偏。
4. **工具扩展受限**：仅支持特化插件接口，缺乏对标准文件系统、Shell 终端等通用编程/系统工具的原生协同。

### 1.2 核心目标
参考知名高扩展性极简 Agent Harness 项目 `@earendil-works/pi` 的设计精髓，在 Python 环境中实现一个架构最简明、高可观测、零黑盒依赖的 **Micro-Harness**：
- **微内核设计**：零多余框架依赖（不使用 LangChain / LlamaIndex / CrewAI），仅基于 Python 3.12+ `asyncio`、`pydantic` 与项目现有的 `httpx`。
- **细粒度事件流**：提供 `agent_start`、`turn_start`、`message_delta`、`tool_call_start`、`tool_call_delta`、`tool_call_end`、`turn_end`、`agent_end` 完整的响应式事件循环。
- **混合增强工具链**：内置标准编程工具（`bash`, `read_file`, `write_file`, `edit_file`, `grep`, `find_files`）及 ATBMind 多模态生图/修图/模板工具（`generate_image`, `refine_image`, `search_templates`）。
- **人在回路 (Steering Queue)**：支持运行中异步队列插话，使 Agent 具备实时转向能力。
- **UI 与存储无缝兼容**：向后兼容现有 SQLite 数据表与 PySide6 桌面端流式展示。

---

## 2. 核心架构与目录组织 (Architecture & Directory Layout)

所有新增模块归属在 `atbmind_core/harness/` 命名空间下，模块结构高度内聚：

```text
atbmind_core/
├── harness/
│   ├── __init__.py             # 导出核心入口: Agent, AgentSession, AgentEvent, AgentTool
│   ├── types.py                # 强类型定义: AgentMessage, Role, ToolCall, AgentEvent, Usage
│   ├── stream.py               # 原生 httpx SSE 流式解析器，增量拼装 tool_calls
│   ├── loop.py                 # 核心双层 Agent 循环状态机 (agent_loop)
│   ├── session.py              # 会话管理器、Steering 队列与 SQLite/Compaction 支持
│   └── tools/
│       ├── __init__.py         # 导出可用工具列表
│       ├── base.py             # AgentTool 基类、Pydantic Schema 生成、ToolResult
│       ├── coding.py           # 编码与系统套件: bash, read, write, edit, grep, find
│       └── domain.py           # ATBMind 领域套件: generate_image, refine_image, search_templates
└── ... (现有模块)
```

---

## 3. 详细设计规格 (Detailed Specifications)

### 3.1 消息契约与事件流 (`types.py`)

#### 消息模型 (`AgentMessage`)
解耦业务渲染上下文与 LLM 协议：
```python
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Dict, List, Optional
import json

class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]

@dataclass
class AgentMessage:
    role: Role
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_llm_dict(self) -> Dict[str, Any]:
        """序列化为符合标准 OpenAI API 格式的字典，剥离内部 metadata"""
        msg: Dict[str, Any] = {"role": self.role.value}
        if self.content is not None:
            msg["content"] = self.content
        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                    },
                }
                for tc in self.tool_calls
            ]
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        if self.name:
            msg["name"] = self.name
        return msg
```

#### 事件模型 (`AgentEvent`)
```python
class AgentEventType(StrEnum):
    AGENT_START = "agent_start"
    TURN_START = "turn_start"
    MESSAGE_START = "message_start"
    MESSAGE_DELTA = "message_delta"      # 携带 token 增量
    MESSAGE_END = "message_end"
    TOOL_CALL_START = "tool_call_start"  # 携带工具名称与入参
    TOOL_CALL_DELTA = "tool_call_delta"  # 携带长工具执行的增量流 (如 bash stdout)
    TOOL_CALL_END = "tool_call_end"      # 携带工具执行结果与元数据
    TURN_END = "turn_end"
    AGENT_END = "agent_end"

@dataclass
class AgentEvent:
    type: AgentEventType
    payload: Dict[str, Any] = field(default_factory=dict)
```

---

### 3.2 传输层与流解析器 (`stream.py`)

实现一个无状态、异步的 SSE 解析器：
1. **请求封装**：
   - 使用 `httpx.AsyncClient`，向指定 `base_url` 发送 POST 请求。
   - 携带 `stream: True`、当前上下文消息列表以及通过工具列表自动生成的 `tools` 声明数组。
2. **分片增量组装 (Incremental Stitching)**：
   - 监听 SSE 行 (`data: {...}`)。
   - 对 `delta.content`，实时 `yield AgentEvent(AgentEventType.MESSAGE_DELTA, {"delta": text})`。
   - 对 `delta.tool_calls`，维护 `dict[index, PartialToolCall]`。将多个数据包中碎片化的 `arguments` 字符串逐段拼接；在收到 `finish_reason == "tool_calls"` 或流结束时，调用 `json.loads` 完成结构化解析。
3. **重试与取消**：
   - 遇到 429 或连接断开时，内置指数退避重试（最多 3 次）。
   - 支持传入 `cancellation_token: asyncio.Event` 实现外部一键取消。

---

### 3.3 工具体系与拦截机制 (`tools/`)

#### 工具基类与 Schema
```python
from enum import StrEnum
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel

class ExecutionMode(StrEnum):
    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"

@dataclass
class ToolResult:
    content: str
    is_error: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    terminate: bool = False

class AgentTool:
    name: str
    description: str
    parameters_schema: Type[BaseModel]
    execution_mode: ExecutionMode = ExecutionMode.PARALLEL

    async def execute(self, args: Dict[str, Any], context: "AgentContext") -> ToolResult:
        raise NotImplementedError

    def to_openai_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema.model_json_schema(),
            },
        }
```

#### 拦截管线 (Hooks)
- `before_tool_call(context, tool_call) -> BeforeToolCallResult`:
  - 检查命令安全性（例如拦截高危 shell 指令）或权限校验。
  - 支持直接短路并返回 error result，阻止危险操作。
- `after_tool_call(context, tool_call, result) -> AfterToolCallResult`:
  - 检查工具输出长度，超长时执行安全截断（防止 prompt 溢出）。
  - 提取富媒体资产（如新生成的图片本地路径）并注入到 `metadata`。

#### 内置工具清单
1. **`bash`**：在隔离子进程中异步执行命令，带超时防护，捕获 stdout/stderr。
2. **`read_file`**：支持指定行范围精确读取文件内容。
3. **`write_file`**：安全写入或覆写本地文件。
4. **`edit_file`**：精准单块替换（TargetContent 必须唯一匹配），杜绝模糊篡改。
5. **`grep` & `find_files`**：代码库快速正则查找与 Glob 文件检索。
6. **`generate_image`**：调用现有 `CloudImageAdapter` / `MockImageAdapter`，输出图片至 `data/generated_images/`。
7. **`refine_image`**：绑定母图的定向增量精修。
8. **`search_templates`**：查询 360 条人像精修模板。

---

### 3.4 核心 Agent Loop 调度 (`loop.py`)

核心逻辑由 `run_agent_loop` 异步生成器提供：
1. **外层循环**：处理用户后续跟进与 Steering 队列。
2. **内层循环**：执行单次任务的多轮推理与工具执行。
   - **Step 1: 准备请求**：调用 `prepare_request`，注入当前系统提示词与有效上下文。
   - **Step 2: 注入 Steering**：检查 `get_steering_messages()`，若有用户中途插话，作为高优先级 UserMessage 追加到上下文末尾。
   - **Step 3: 流式调用 LLM**：触发 `stream.py`，持续转发 `MESSAGE_DELTA`。
   - **Step 4: 工具调度**：
     - 若模型返回工具调用列表：
       - 执行 `before_tool_call` 预检。
       - 判断批次工具模式：若任意工具标记为 `SEQUENTIAL`，全批次采用串行执行；否则采用 `asyncio.gather` 并发执行。
       - 逐个执行并发出 `TOOL_CALL_END`。
       - 执行 `after_tool_call` 结果处理。
       - 将所有工具执行结果转化为 `role=TOOL` 的 `AgentMessage` 并写入上下文。
       - 若所有工具结果均包含 `terminate=True`，跳出内层循环。
     - 若模型未返回工具调用（仅文本回复）：
       - 当前轮次结束。若无待消费的 Steering 消息，跳出循环。
3. **终止结算**：触发 `agent_end`，输出本次任务产生的所有新消息及 Token 用量统计。

---

### 3.5 会话管理与存储适配 (`session.py`)

1. **`AgentSession`**：
   - 维护当前会话的 `session_id`、消息列表 `messages`、工具注册表 `tools` 以及 Steering 队列。
   - 提供 `session.prompt(text)` 简易启动方法与 `session.send_steering(text)` 插话方法。
2. **Compaction（上下文智能修剪）**：
   - 估算当前上下文 Token 占用。
   - 当达到设定阈值（例如 32k/64k 上限的 75%）时，自动将历史轮次的冗长 Tool 结果提炼压缩，保留最新的 $K$ 轮原轮次，确保多轮持续对话不会 OOM 或报错。
3. **SQLite 存储双向同步**：
   - 产生 `turn_end` 时，将格式化消息存入 `data/atbmind.db` 的 `messages` 表。
   - 支持从现有数据库会话无缝加载恢复 `AgentSession`。

---

### 3.6 桌面端 PySide6 UI 桥接 (`apps/atbmind_desktop/workers.py`)

改造 `GenerationWorker`（继承自 `QThread`）：
- 在工作线程内部启动 `asyncio.run(self._run_harness())`。
- 监听 `AgentEvent` 并发射相应 Qt Signal：
  - `MESSAGE_DELTA` -> 发送 `token_received(session_id, delta)`，中央对话流实时打字机输出。
  - `TOOL_CALL_START` -> 发送 `tool_started(session_id, tool_name, args)`，展示“正在运行工具...”卡片。
  - `TOOL_CALL_DELTA` -> 发送 `tool_progress(session_id, chunk)`，实时刷新终端输出。
  - `TOOL_CALL_END` -> 发送 `tool_finished(session_id, tool_name, metadata)`，若是图片工具，即刻渲染高颜值 `DrawResultCard`（包含对比图与微调按钮）。
  - `AGENT_END` -> 发送 `generation_finished(session_id, final_text)`。

---

## 4. 测试与验证策略 (Testing & Verification Strategy)

创建自动化测试套件 `tests/test_harness/`：
1. **`test_types.py`**：验证 `AgentMessage` 与 OpenAI 报文双向无损转换。
2. **`test_stream.py`**：使用 Mock 异步流，验证 SSE 数据包切分、乱序组装与 `tool_calls` 参数碎片拼接。
3. **`test_tools.py`**：
   - 测试 `bash` 工具执行、返回码与超时判定。
   - 测试 `read_file`、`write_file`、`edit_file`（精确匹配替换成功与失败路径）。
   - 测试 `generate_image` 与 Mock 适配器的桥接。
4. **`test_loop.py`**：
   - Mock LLM 下的多轮连续 Tool 调用与自愈流程。
   - 工具 `parallel` 并发与 `sequential` 串行执行顺序验证。
   - 运行中通过 `send_steering` 插话的有效性验证。
   - `terminate: True` 提前终止判定。
5. **回归集成测试**：
   - 运行全局测试套件：`PYTHONPATH=. pytest tests/`，保证原有数据库操作与桌面逻辑 100% 通过。

---

## 5. 迁移与兼容性保障 (Migration Plan)

- **无破坏性演进**：保留原有 `atbmind_core/engine/` 模块，新增 `atbmind_core/harness/` 作为升级版引擎。
- **无缝回滚能力**：`GenerationWorker` 可通过配置项 `engine_type: "harness" | "legacy_3layer"` 进行无缝灰度切换。
