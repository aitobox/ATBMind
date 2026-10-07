# Pi-Style Micro-Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 参考知名项目 `@earendil-works/pi` 架构逻辑，在 Python 中实现极简可扩展的 Agent Harness，并作为 ATBMind 的新一代流式执行内核。

**Architecture:** 采用微内核设计模式，将消息与事件模型（`types.py`）、SSE 原生流解析（`stream.py`）、可拦截工具体系（`tools/`）、双层事件循环（`loop.py`）以及会话管理（`session.py`）完全解耦，并通过 `apps/atbmind_desktop/workers.py` 驱动 PySide6 客户端的实时打字机 Token 流和工具进度卡片。

**Tech Stack:** Python 3.12+, `pydantic>=2.6.0`, `httpx>=0.27.0`, `pyside6>=6.6.0`, `pytest>=8.0.0`, `pytest-asyncio>=0.23.0`

**Spec:** [docs/superpowers/specs/2026-10-07-pi-harness-port-design.md](file:///Users/brainzhang/work/aitobox/ATBMind/docs/superpowers/specs/2026-10-07-pi-harness-port-design.md)

## Global Constraints

- 严禁引入 LangChain, LlamaIndex, CrewAI 等外部重型 Agent 框架；
- 仅复用项目现有 `httpx`, `pydantic`, `pytest` 等依赖；
- Python 异步调用必须遵循标准 `asyncio` 规范，支持 `async for event in agent.run(...)`；
- 所有代码测试命令使用: `PYTHONPATH=. pytest tests/test_harness/`；
- 保持向后兼容：不破坏现有 SQLite 数据表结构与旧版测试。

## Review Focus

1. **Tool Calls 流式碎片断裂拼装**：LLM 在 SSE 中返回分段 `arguments` JSON 字符串可能跨越多个数据包，必须在反序列化前完整累加缓存并具备异常容错。
2. **工具执行异常不抛出中断**：任何工具（如 `bash` 退出码非 0 或文件不存在）执行失败均必须封装为 `is_error=True` 的 `ToolResult`，不得导致 Agent 循环崩溃。
3. **高危命令拦截**：`before_tool_call` 必须能够拦截非法操作并返回短路结果，阻止危险系统命令执行。
4. **Steering 队列线程安全与及时注入**：在桌面端异步线程中，外部动态调用的 `send_steering` 必须在内层循环的下一轮前被消费，不得丢失。
5. **UI 主线程防死锁与非阻塞**：PySide6 `GenerationWorker` 中运行 `asyncio.run()` 时必须通过 Qt Signal 跨线程通信，不能直接在子线程修改 UI 或阻塞 Qt 主事件循环。

---

### Task 1: 消息模型与事件契约 (`types.py`)

**Files:**
- Create: `atbmind_core/harness/types.py`
- Create: `tests/test_harness/test_types.py`

**Interfaces:**
- Consumes: `pydantic`, `dataclasses`
- Produces: `Role`, `ToolCall`, `AgentMessage`, `AgentEventType`, `AgentEvent`, `Usage`

- [ ] **Step 1: Write the failing test**
  编写测试验证 `AgentMessage` 对 `user`, `assistant`, `tool` 各角色报文的双向转换，验证包含 `tool_calls` 时的序列化与反序列化，验证 `AgentEvent` 类型枚举。

- [ ] **Step 2: Run test to verify it fails**
  Run: `pytest tests/test_harness/test_types.py -v`
  Expected: FAIL with `ModuleNotFoundError: No module named 'atbmind_core.harness'`

- [ ] **Step 3: Implement `types.py`**
  实现 `Role`, `ToolCall`, `AgentMessage`（包含 `to_llm_dict()` 与从 OpenAI 字典加载的辅助方法），定义 `AgentEventType` 与 `AgentEvent`。

- [ ] **Step 4: Run test to verify it passes**
  Run: `pytest tests/test_harness/test_types.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**
  ```bash
  git add atbmind_core/harness/types.py tests/test_harness/test_types.py
  git commit -m "feat(harness): implement AgentMessage and AgentEvent types"
  ```

---

### Task 2: 原生 SSE 流式传输与 Tool Calls 增量组装 (`stream.py`)

**Files:**
- Create: `atbmind_core/harness/stream.py`
- Create: `tests/test_harness/test_stream.py`

**Interfaces:**
- Consumes: `httpx.AsyncClient`, `AgentMessage`, `ToolCall`, `AgentEvent`
- Produces: `StreamClient`, `StreamResponseChunk`

- [ ] **Step 1: Write the failing test**
  使用 Mock 传输模拟 SSE 流：包含文本流式输出、分片 `tool_calls` 参数拼装、连接异常指数退避重试，以及取消令牌取消。

- [ ] **Step 2: Run test to verify it fails**
  Run: `pytest tests/test_harness/test_stream.py -v`
  Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `StreamClient` in `stream.py`**
  基于 `httpx.AsyncClient` 实现异步生成器 `stream_chat(messages, tools, options)`，自动按索引合并 `tool_calls[i].function.arguments` 片段并在完成时反序列化为 JSON，向外发出增量事件。

- [ ] **Step 4: Run test to verify it passes**
  Run: `pytest tests/test_harness/test_stream.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**
  ```bash
  git add atbmind_core/harness/stream.py tests/test_harness/test_stream.py
  git commit -m "feat(harness): implement native SSE stream parser with tool call stitching"
  ```

---

### Task 3: 工具抽象基类与标准编程套件 (`tools/base.py`, `coding.py`)

**Files:**
- Create: `atbmind_core/harness/tools/base.py`
- Create: `atbmind_core/harness/tools/coding.py`
- Create: `tests/test_harness/test_tools_coding.py`

**Interfaces:**
- Consumes: `pydantic.BaseModel`, `ExecutionMode`
- Produces: `AgentTool`, `ToolResult`, `BashTool`, `ReadFileTool`, `WriteFileTool`, `EditFileTool`, `GrepTool`, `FindFilesTool`

- [ ] **Step 1: Write the failing test**
  编写测试覆盖各个编程工具：`bash` 执行与超时处理、`read_file` 行号区间读取、`write_file` 写入、`edit_file` 精确匹配替换（以及不唯一匹配时的失败保护）、`grep` 正则检索。

- [ ] **Step 2: Run test to verify it fails**
  Run: `pytest tests/test_harness/test_tools_coding.py -v`
  Expected: FAIL

- [ ] **Step 3: Implement `base.py` and `coding.py`**
  定义 `AgentTool` 抽象基类及 Pydantic Schema 自动转换，实现 6 个核心系统与代码操作工具，所有工具均返回标准 `ToolResult`。

- [ ] **Step 4: Run test to verify it passes**
  Run: `pytest tests/test_harness/test_tools_coding.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**
  ```bash
  git add atbmind_core/harness/tools/base.py atbmind_core/harness/tools/coding.py tests/test_harness/test_tools_coding.py
  git commit -m "feat(harness): implement AgentTool base and coding toolset"
  ```

---

### Task 4: ATBMind 领域工具套件 (`tools/domain.py`)

**Files:**
- Create: `atbmind_core/harness/tools/domain.py`
- Create: `tests/test_harness/test_tools_domain.py`

**Interfaces:**
- Consumes: `AgentTool`, `ToolResult`, `MockImageAdapter`, `CloudImageAdapter`
- Produces: `GenerateImageTool`, `RefineImageTool`, `SearchTemplatesTool`

- [ ] **Step 1: Write the failing test**
  测试通过 Mock 图像适配器调用 `GenerateImageTool` 与 `RefineImageTool`，验证生成的图片本地路径和元数据注入；测试 `SearchTemplatesTool` 检索。

- [ ] **Step 2: Run test to verify it fails**
  Run: `pytest tests/test_harness/test_tools_domain.py -v`
  Expected: FAIL

- [ ] **Step 3: Implement `domain.py`**
  封装 ATBMind 原有生图与模板能力为符合 `AgentTool` 规范的领域工具，输出结果中附带 `metadata["image_path"]` 与相关展示参数。

- [ ] **Step 4: Run test to verify it passes**
  Run: `pytest tests/test_harness/test_tools_domain.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**
  ```bash
  git add atbmind_core/harness/tools/domain.py tests/test_harness/test_tools_domain.py
  git commit -m "feat(harness): bridge ATBDraw adapters and templates as AgentTools"
  ```

---

### Task 5: 核心 Agent Loop 状态机 (`loop.py`)

**Files:**
- Create: `atbmind_core/harness/loop.py`
- Create: `tests/test_harness/test_loop.py`

**Interfaces:**
- Consumes: `AgentMessage`, `AgentEvent`, `StreamClient`, `AgentTool`, `before_tool_call`, `after_tool_call`
- Produces: `agent_loop(prompts, context, config, signal) -> AsyncIterator[AgentEvent]`

- [ ] **Step 1: Write the failing test**
  编写状态机测试：
  - 单轮对话与纯文本流式输出；
  - 自动触发工具执行并进行多轮纠错；
  - 并发工具（`parallel`）与串行工具（`sequential`）的调度模式验证；
  - 动态 Steering 插话注入验证；
  - `terminate: True` 拦截提前退出。

- [ ] **Step 2: Run test to verify it fails**
  Run: `pytest tests/test_harness/test_loop.py -v`
  Expected: FAIL

- [ ] **Step 3: Implement `loop.py`**
  实现内外双层循环、Hooks 拦截执行、并发 `asyncio.gather` 与串行调度，产出规范的 `AgentEvent` 异步流。

- [ ] **Step 4: Run test to verify it passes**
  Run: `pytest tests/test_harness/test_loop.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**
  ```bash
  git add atbmind_core/harness/loop.py tests/test_harness/test_loop.py
  git commit -m "feat(harness): implement core Agent Loop with hooks and steering"
  ```

---

### Task 6: 会话管理与 SQLite/Compaction 持久化 (`session.py`)

**Files:**
- Create: `atbmind_core/harness/session.py`
- Modify: `atbmind_core/harness/__init__.py`
- Create: `tests/test_harness/test_session.py`

**Interfaces:**
- Consumes: `agent_loop`, `atbmind_core.storage.sqlite_manager`
- Produces: `AgentSession`, `CompactionConfig`

- [ ] **Step 1: Write the failing test**
  测试 `AgentSession` 初始化、绑定工具、执行任务、会话多轮历史持久化保存至 SQLite，以及超长历史下的 Compaction 压缩剪枝。

- [ ] **Step 2: Run test to verify it fails**
  Run: `pytest tests/test_harness/test_session.py -v`
  Expected: FAIL

- [ ] **Step 3: Implement `session.py`**
  实现 `AgentSession` 统一管理历史消息、工具列表与异步 Steering 队列，无缝对接现有数据库读写。

- [ ] **Step 4: Run test to verify it passes**
  Run: `pytest tests/test_harness/test_session.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**
  ```bash
  git add atbmind_core/harness/session.py atbmind_core/harness/__init__.py tests/test_harness/test_session.py
  git commit -m "feat(harness): implement AgentSession and SQLite persistence adapter"
  ```

---

### Task 7: 桌面端 PySide6 Worker 桥接与流式展示 (`workers.py`)

**Files:**
- Modify: `apps/atbmind_desktop/workers.py`
- Create: `tests/test_harness/test_worker_bridge.py`

**Interfaces:**
- Consumes: `AgentSession`, `AgentEvent`, `QThread`
- Produces: `GenerationWorker.token_received`, `tool_started`, `tool_finished`

- [ ] **Step 1: Write the failing test**
  测试 `GenerationWorker` 在子线程中执行 `AgentSession`，验证其通过 Qt 信号派发打字机 Token 与工具执行完成事件。

- [ ] **Step 2: Run test to verify it fails**
  Run: `pytest tests/test_harness/test_worker_bridge.py -v`
  Expected: FAIL

- [ ] **Step 3: Update `GenerationWorker` in `workers.py`**
  接入 `AgentSession`，在异步任务执行中监听 `AgentEvent` 并发射相应的 Qt 信号，驱动界面打字机效果与结果卡片。

- [ ] **Step 4: Run test to verify it passes**
  Run: `pytest tests/test_harness/test_worker_bridge.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**
  ```bash
  git add apps/atbmind_desktop/workers.py tests/test_harness/test_worker_bridge.py
  git commit -m "feat(desktop): connect GenerationWorker with Pi-style agent harness"
  ```

---

### Task 8: 全局回归与端到端集成测试

**Files:**
- Create: `tests/test_harness/test_integration.py`

**Interfaces:**
- Consumes: 全模块
- Produces: 全系统端到端测试绿灯

- [ ] **Step 1: Write the end-to-end integration test**
  编写完整会话链路测试：从用户 Prompt 触发，经过模型思考打字机输出、调用 `generate_image` 生图工具、写入 SQLite 数据库、再进行第二轮微调。

- [ ] **Step 2: Run end-to-end and regression tests**
  Run: `PYTHONPATH=. pytest tests/`
  Expected: 包含原有 52+ 测试与新增所有 Harness 测试全部 PASS。

- [ ] **Step 3: Commit**
  ```bash
  git add tests/test_harness/test_integration.py
  git commit -m "test(harness): add end-to-end integration tests and verify full suite"
  ```
