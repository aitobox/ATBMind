# Octop 架构演进（阶段一：核心内核与交互升级）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地借鉴自 TencentCloud/Octop 的两大核心架构特性：UI Artifact 旁路中间件（防模型上下文膨胀）与 RobotTeam 2.0（主持人调度准则 + 任务定制改写 + 桌面真群聊流式上墙）。

**Architecture:** 
1. 在 `atbmind_core/harness/middleware/artifact_offload.py` 中引入 `ArtifactOffloadMiddleware`，拦截并剥离大尺寸结构体数据至 `ToolResult.artifact`，保持 LLM Prompt 极简；
2. 升级 `atbmind_core/roles/`，收窄 Coordinator 权限至调度/短期记忆，注入 Anti-Pass-Through 任务改写和 `compose_followup` 闭环机制；
3. 改造桌面端 `ChatStreamView` 与事件总线，流式帧透传 `speaker_role`，呈现多专家身份徽章并列上墙。

**Tech Stack:** Python 3.12+, PySide6, Pydantic v2, pytest

**Spec:** [docs/superpowers/specs/2026-10-08-octop-architecture-adoption-design.md](file:///Users/brainzhang/work/aitobox/ATBMind/docs/superpowers/specs/2026-10-08-octop-architecture-adoption-design.md)

## Global Constraints

- 遵循单进程极简设计，不引入外部队列与外部网络依赖；
- 保持现有 338 项测试全部通过（无回归）；
- `ToolResult.artifact` 在进入大模型推理前必须严格剔除，仅在客户端展示和 SQLite 存储中保留；
- Coordinator 严禁装备执行性重型工具（生图、文件修改、命令行执行）。

## Review Focus

- **Payload 大小边界**：低于阈值（如 3000 字符）或无 UI 标记的工具输出不被误剥离；
- **并发与异常兜底**：当工具抛出异常或返回非结构化文本时，中间件平滑透传，不中断 `agent_loop`；
- **任务改写防空传**：Coordinator 不得直接转发用户原话，必须包含任务目标、约束与格式；
- **群聊发言人识别**：当多个专家交替输出时，UI 流式气泡能准确根据 `speaker_role` 切换头像和样式，不产生串台；
- **历史回放一致性**：重新打开会话时，能够从包含 `artifact` 的历史消息中正确还原卡片渲染。

---

### Task 1: 实现 `ToolResult` Artifact 结构扩展与模型转换适配

**Files:**
- Create: `tests/test_artifact_offload.py`
- Modify: `atbmind_core/harness/types.py`
- Modify: `atbmind_core/harness/session.py`

**Interfaces:**
- Consumes: `ToolResult` 模型基类
- Produces: `ToolResult.artifact: dict[str, Any] | None` 字段；`to_model_message()` 方法确保剔除 `artifact`

- [ ] **Step 1: 编写失败测试**
验证 `ToolResult` 接受 `artifact` 字段，且转化为 LLM 请求消息时不包含 `artifact`。

- [ ] **Step 2: 运行测试验证失败**
Run: `conda run -n ATBMind python -m pytest tests/test_artifact_offload.py -v`
Expected: FAIL (missing field or method)

- [ ] **Step 3: 实现 `ToolResult` 字段与转换逻辑**
在 `atbmind_core/harness/types.py` 为 `ToolResult` 添加 `artifact: dict[str, Any] | None = None`，并实现过滤逻辑。

- [ ] **Step 4: 运行测试验证通过**
Run: `conda run -n ATBMind python -m pytest tests/test_artifact_offload.py -v`
Expected: PASS

- [ ] **Step 5: 提交代码**
`git add atbmind_core/harness/types.py tests/test_artifact_offload.py && git commit -m "feat(harness): extend ToolResult with artifact payload field"`

---

### Task 2: 实现 `ArtifactOffloadMiddleware` 拦截与数据分离中间件

**Files:**
- Create: `atbmind_core/harness/middleware/__init__.py`
- Create: `atbmind_core/harness/middleware/artifact_offload.py`
- Modify: `tests/test_artifact_offload.py`
- Modify: `atbmind_core/harness/loop.py`

**Interfaces:**
- Consumes: `ToolResult`
- Produces: `ArtifactOffloadMiddleware.process_tool_result(result: ToolResult) -> ToolResult`

- [ ] **Step 1: 编写失败测试**
测试对长内容（$\ge 3000$ 字符）且带有 `atbmind_ui` 声明的 JSON 字符串进行原地剥离：`data` 移至 `artifact`，`content` 替换为摘要 + `data_ref: "artifact"`。

- [ ] **Step 2: 运行测试验证失败**
Run: `conda run -n ATBMind python -m pytest tests/test_artifact_offload.py -k test_middleware -v`
Expected: FAIL

- [ ] **Step 3: 实现 `ArtifactOffloadMiddleware`**
编写 `ArtifactOffloadMiddleware`，挂载进 `agent_loop` 的工具后处理拦截链。

- [ ] **Step 4: 运行测试验证通过**
Run: `conda run -n ATBMind python -m pytest tests/test_artifact_offload.py -v`
Expected: PASS

- [ ] **Step 5: 提交代码**
`git add atbmind_core/harness/middleware/ tests/test_artifact_offload.py && git commit -m "feat(harness): add ArtifactOffloadMiddleware for large UI payload extraction"`

---

### Task 3: 强化 Coordinator 调度准则、任务改写与收口机制

**Files:**
- Create: `tests/test_coordinator_rules.py`
- Modify: `atbmind_core/roles/delegation.py`
- Modify: `roles/coordinator.json`
- Modify: `atbmind_core/roles/team.py`

**Interfaces:**
- Consumes: `RobotRole`、`delegate_task`
- Produces: `Coordinator` 专属 Prompt 模板、剥离直接执行工具校验、`compose_followup` 闭环收口函数

- [ ] **Step 1: 编写失败测试**
验证 Coordinator 角色被实例化时自动剥除 `generate_image` 等重型工作工具，且 `delegate_task` 返回后触发 `compose_followup`。

- [ ] **Step 2: 运行测试验证失败**
Run: `conda run -n ATBMind python -m pytest tests/test_coordinator_rules.py -v`
Expected: FAIL

- [ ] **Step 3: 优化 Coordinator 角色配置与调度协议**
更新 `roles/coordinator.json` 的 Prompt 注入 Anti-Pass-Through 准则与红线；在 `delegation.py` 中引入 `compose_followup` 逻辑。

- [ ] **Step 4: 运行测试验证通过**
Run: `conda run -n ATBMind python -m pytest tests/test_coordinator_rules.py -v`
Expected: PASS

- [ ] **Step 5: 提交代码**
`git add atbmind_core/roles/ roles/coordinator.json tests/test_coordinator_rules.py && git commit -m "feat(roles): enforce coordinator delegation guidelines and followup synthesis"`

---

### Task 4: 桌面端 `ChatStreamView` 多专家流式身份上墙与徽章渲染

**Files:**
- Create: `tests/test_stream_speaker.py`
- Modify: `apps/atbmind_desktop/widgets/chat_stream.py`
- Modify: `apps/atbmind_desktop/widgets/message_bubble.py`
- Modify: `atbmind_core/runtime/event_bus.py`

**Interfaces:**
- Consumes: `TeamStreamChunk(speaker_role_id, speaker_name, chunk_type, payload)`
- Produces: 桌面聊天流式视窗内按发言人角色渲染专属头像、角色徽章与并列气泡

- [ ] **Step 1: 编写事件冒泡与角色标记测试**
测试当子专家执行时，`EventBus` 发送的事件携带 `speaker_role` 字段。

- [ ] **Step 2: 运行测试验证失败**
Run: `conda run -n ATBMind python -m pytest tests/test_stream_speaker.py -v`
Expected: FAIL

- [ ] **Step 3: 实现事件透传与 UI 气泡渲染扩展**
在 `message_bubble.py` 中支持 `speaker_role` 徽章渲染，并在 `chat_stream.py` 中实现多专家气泡交替流式追加。

- [ ] **Step 4: 运行测试验证通过**
Run: `conda run -n ATBMind python -m pytest tests/test_stream_speaker.py -v`
Expected: PASS

- [ ] **Step 5: 提交代码**
`git add apps/atbmind_desktop/ atbmind_core/runtime/ tests/test_stream_speaker.py && git commit -m "feat(ui): add multi-expert stream speaker badges and group chat relay"`

---

### Task 5: 全量回归与端到端验证

- [ ] **Step 1: 执行全量测试套件**
Run: `conda run -n ATBMind python -m pytest tests/`
Expected: PASS (全部通过，340+ 测试通过)

- [ ] **Step 2: 验证 Payload 剥离与模型 Token 减少率**
验证带有富卡片数据的生图流程，确认模型上下文无冗余 Payload 污染。
