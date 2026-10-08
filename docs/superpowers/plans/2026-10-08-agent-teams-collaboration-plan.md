# AgentTeams（真群聊与主持人派工多专家协同模式）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 系统性落地借鉴自 TencentCloud/Octop 的 **AgentTeams** 架构创新，在 ATBMind 中构建“带主持人的真群聊（Host-based Group Chat）”多专家协同体系：包含异步非阻塞派工、内存任务追踪器（`TeamJobTracker`）、会话 Checkpoint 投影隔离、以及前端群聊时间线多路流式上墙。

**Architecture:** 
1. **调度中枢与在途任务追踪**：在 `atbmind_core/roles/jobs.py` 中引入 `TeamJobTracker`，追踪并发专家在途任务的完整生命周期；
2. **异步并行派工与闭环回叫**：重构 `atbmind_core/roles/delegation.py`，支持主持人单轮非阻塞并行 `dispatch` 多位专家，子专家在后台异步执行并向总线流式广播，执行完毕触发 `compose_followup` 唤醒主持人；
3. **会话与 Checkpoint 投影隔离**：在 `atbmind_core/roles/projection.py` 中定义房间 ID 与成员虚拟子会话隔离机制（`room_session~role_id`），消息体元数据注入 `speaker_role` 与发言人身份；
4. **桌面端真群聊时间线**：升级 `ChatStreamView`，多路接收多专家流式帧，实现自然交替呈现的群聊气泡与在途执行状态卡片。

**Tech Stack:** Python 3.12+, PySide6, asyncio, Pydantic v2, pytest

**Spec:** [docs/superpowers/specs/2026-10-08-octop-architecture-adoption-design.md](file:///Users/brainzhang/work/aitobox/ATBMind/docs/superpowers/specs/2026-10-08-octop-architecture-adoption-design.md)（模块二：RobotTeam 2.0 真群聊与协调员准则）

## Global Constraints

- 遵循单进程极简设计，不引入 Celery、Redis 等外部重型消息队列；
- 主持人（Coordinator）坚决不授予任何执行类重型工具（写文件、运行命令、生图、代码解析），仅保留团队调度与记忆检索工具；
- 成员专家禁止反向递归在群聊中拉人派工（防止 Multi-Agent 死循环）；
- 有在途任务进行中时，锁定团队编制变更；
- 保持全部既有 352+ 项测试 100% 通过（零回归）。

## Review Focus

1. **并行派工并发安全**：当主持人一轮对话调用多次派工向多个专家分发任务时，各专家的 `agent_loop` 协程应能真正并行运行，事件总线互不串流、不发生竞态覆盖；
2. **在途任务锁与状态释放**：无论专家任务成功、抛出异常还是被取消，`TeamJobTracker` 必须严格释放活跃锁，防止任务永远卡在 PENDING/RUNNING；
3. **主持人收尾防复述**：回叫唤醒主持人时，注入的 followup prompt 必须严格约束其只判断“任务是否达到用户期望”并给出不超过 3 句的精简总结，严禁长篇大论复述专家已上墙的成果；
4. **群聊时间线分流渲染**：当专家 A 与专家 B 异步并发输出时，桌面端 `ChatStreamView` 必须基于 `origin_role` / `speaker_role` 区分流式帧，不得把两个专家的流式文字拼成一个乱序气泡；
5. **历史持久化一致性**：在重新加载房间历史会话时，能够从包含 `speaker_role` 元数据的消息中准确还原群聊讨论流，多专家头像与名称无错乱。

---

### Task 1: 实现团队在途派工追踪器 `TeamJobTracker` 与异步任务模型

**Files:**
- Create: `atbmind_core/roles/jobs.py`
- Create: `tests/test_team_jobs.py`

**Interfaces:**
- Consumes: `pydantic.BaseModel`, `datetime`
- Produces: 
  - `TeamJobStatus(str, Enum)`: `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`
  - `TeamJob(BaseModel)`: `job_id: str`, `role_id: str`, `task_description: str`, `status: TeamJobStatus`, `result: Optional[str]`, `error: Optional[str]`, `created_at: float`
  - `TeamJobTracker`:
    - `submit_job(role_id: str, task_description: str) -> TeamJob`
    - `start_job(job_id: str) -> None`
    - `complete_job(job_id: str, result: str) -> None`
    - `fail_job(job_id: str, error: str) -> None`
    - `get_job(job_id: str) -> Optional[TeamJob]`
    - `list_active_jobs(role_id: Optional[str] = None) -> list[TeamJob]`
    - `has_active_jobs(role_id: Optional[str] = None) -> bool`

- [ ] **Step 1: 编写失败测试**

在 `tests/test_team_jobs.py` 中测试 `TeamJobTracker` 的任务创建、状态流转、并发任务查询与在途任务锁判定。

- [ ] **Step 2: 运行测试验证失败**

Run: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_team_jobs.py -v`  
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: 实现 `TeamJobTracker`**

在 `atbmind_core/roles/jobs.py` 中实现内存级线程安全的任务追踪器。

- [ ] **Step 4: 运行测试验证通过**

Run: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_team_jobs.py -v`  
Expected: PASS

- [ ] **Step 5: 提交代码**

```bash
git add atbmind_core/roles/jobs.py tests/test_team_jobs.py
git commit -m "feat(roles): implement TeamJobTracker for multi-agent in-flight dispatch tracking"
```

---

### Task 2: 改造派工工具支持异步非阻塞派发与后台并发执行

**Files:**
- Modify: `atbmind_core/roles/delegation.py`
- Modify: `atbmind_core/roles/team.py`
- Create: `tests/test_async_delegation.py`

**Interfaces:**
- Consumes: `TeamJobTracker`, `TeamJob`, `agent_loop`
- Produces: 
  - `DelegateTaskTool`:
    - 支持可选参数 `async_mode: bool = False`（默认向后兼容，但支持异步非阻塞派发）
    - 在异步模式下：调用即在 `TeamJobTracker` 注册任务，发起后台 `asyncio.create_task` 启动子循环，并立即返回 `ToolResult(content="任务已派发给专家...", metadata={"job_id": ...})`
  - 子专家执行过程中产生事件时，每帧封装为带 `speaker_role: role_id` 的事件冒泡；
  - 执行完毕后更新 `TeamJobTracker`，并调用 `on_specialist_done` 触发协调员唤醒。

- [ ] **Step 1: 编写失败测试**

在 `tests/test_async_delegation.py` 中测试：
1. 异步派工工具立即返回，不阻塞主任务循环；
2. 后台子专家协程独立执行，流出带有 `speaker_role` 标记的事件；
3. 子任务结束自动更新 tracker 并生成标准的 `compose_followup` 闭环通知。

- [ ] **Step 2: 运行测试验证失败**

Run: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_async_delegation.py -v`  
Expected: FAIL

- [ ] **Step 3: 改造 `DelegateTaskTool` 与 `RobotTeam` 运行时调度**

修改 `atbmind_core/roles/delegation.py` 与 `team.py`，支持在 `RobotTeam` 中挂载 `TeamJobTracker`，并提供后台任务生命周期监控方法。

- [ ] **Step 4: 运行测试验证通过**

Run: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_async_delegation.py -v`  
Expected: PASS

- [ ] **Step 5: 提交代码**

```bash
git add atbmind_core/roles/delegation.py atbmind_core/roles/team.py tests/test_async_delegation.py
git commit -m "feat(roles): enhance delegation with non-blocking async dispatch and event bubble"
```

---

### Task 3: 实现会话 Checkpoint 投影隔离与发言人元数据映射

**Files:**
- Create: `atbmind_core/roles/projection.py`
- Create: `tests/test_team_projection.py`
- Modify: `atbmind_core/roles/team.py`

**Interfaces:**
- Consumes: `AgentMessage`, `Role`
- Produces: 
  - `derive_member_session_id(room_session_id: str, role_id: str) -> str`：派生虚拟隔离子会话键（如 `room_123~draw_expert`）
  - `tag_message_speaker(msg: AgentMessage, speaker_role: str, speaker_name: str, avatar: str = "") -> AgentMessage`
  - `project_member_turn_to_room(member_messages: list[AgentMessage], speaker_role: str, speaker_name: str) -> list[AgentMessage]`

- [ ] **Step 1: 编写失败测试**

在 `tests/test_team_projection.py` 中测试子会话 ID 生成规则、消息发言人元数据打标、以及将成员内部执行的多条消息投影映射为群聊房间可见消息的过滤规则。

- [ ] **Step 2: 运行测试验证失败**

Run: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_team_projection.py -v`  
Expected: FAIL

- [ ] **Step 3: 实现投影映射与子会话隔离逻辑**

在 `atbmind_core/roles/projection.py` 中实现规范投影转换器，并在 `team.py` 中进行装配。

- [ ] **Step 4: 运行测试验证通过**

Run: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_team_projection.py -v`  
Expected: PASS

- [ ] **Step 5: 提交代码**

```bash
git add atbmind_core/roles/projection.py tests/test_team_projection.py
git commit -m "feat(roles): add session checkpoint projection and speaker metadata tagging"
```

---

### Task 4: 桌面端群聊时间线并发流式多路分流渲染 (`ChatStreamView`)

**Files:**
- Modify: `apps/atbmind_desktop/widgets/chat_stream.py`
- Modify: `apps/atbmind_desktop/widgets/message_bubble.py`
- Create: `tests/test_desktop_group_chat_stream.py`

**Interfaces:**
- Consumes: `AgentEvent`, `speaker_role`, `speaker_name`
- Produces: 
  - `ChatStreamView` 增加活跃发言人多路状态机：
    - 支持同时追踪多个活跃专家流式气泡（`_active_bubbles: dict[str, MessageBubble]`）
    - 当收到 `speaker_role` 发生切换的 token 事件时，精准路由至对应专家的气泡进行增量追加，不出现混淆覆盖
  - `MessageBubble` 顶部展示角色身份徽章（主持人标签 vs 专家标签），并展示专属头像。

- [ ] **Step 1: 编写失败测试**

在 `tests/test_desktop_group_chat_stream.py` 中利用 pytest-qt 测试：模拟交替到来的专家 A 与专家 B 的流式 token 事件，验证生成了两个独立的专用气泡且文本内容各自正确。

- [ ] **Step 2: 运行测试验证失败**

Run: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_desktop_group_chat_stream.py -v`  
Expected: FAIL

- [ ] **Step 3: 改造 `ChatStreamView` 多路分流逻辑**

重构 `apps/atbmind_desktop/widgets/chat_stream.py` 中的 `handle_stream_event`，引入按 `speaker_role` 分发的多气泡路由表。

- [ ] **Step 4: 运行测试验证通过**

Run: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_desktop_group_chat_stream.py -v`  
Expected: PASS

- [ ] **Step 5: 提交代码**

```bash
git add apps/atbmind_desktop/widgets/chat_stream.py apps/atbmind_desktop/widgets/message_bubble.py tests/test_desktop_group_chat_stream.py
git commit -m "feat(desktop): enable multi-speaker multiplexed streaming in ChatStreamView"
```

---

### Task 5: 端到端协同调度与全量防回归验证

**Files:**
- Create: `tests/test_agent_teams_e2e.py`
- Test: 全量测试套件 `tests/`

- [ ] **Step 1: 编写端到端团队协作集成测试**

在 `tests/test_agent_teams_e2e.py` 中构造完整流程：用户向 Coordinator 提问 -> Coordinator 改写为任务书并调用异步 delegate -> 专家后台运行产生输出上墙 -> Coordinator 收到完成回叫并精简收工，断言全链路事件与最终消息。

- [ ] **Step 2: 运行端到端集成测试**

Run: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_agent_teams_e2e.py -v`  
Expected: PASS

- [ ] **Step 3: 运行全量测试套件防回归**

Run: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/`  
Expected: ALL PASS（360+ tests passing, 0 failures）

- [ ] **Step 4: 提交代码与文档更新**

```bash
git add tests/test_agent_teams_e2e.py docs/superpowers/plans/2026-10-08-agent-teams-collaboration-plan.md
git commit -m "test: add e2e integration tests for AgentTeams host-based group chat"
```
