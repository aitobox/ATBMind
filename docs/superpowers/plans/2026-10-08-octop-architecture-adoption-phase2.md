# Octop 架构演进（阶段二：执行后端、上下文压缩与人格系统）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 吸收 TencentCloud/Octop 与 `octop-harness` 的三项核心生产级设计：执行环境抽象层（BackendProtocol 与沙箱边界防护）、上下文自适应滚动压缩中间件（ContextCompactionMiddleware）、以及 16 种 MBTI 强类型人格与行为范式映射系统（PersonaLoader）。

**Architecture:** 
1. 在 `atbmind_core/harness/backends/` 中建立统一的 `BackendProtocol`，将命令执行与文件 I/O 从工具层解耦，赋予工具宿主越界防护与容器沙箱扩展能力；
2. 在 `atbmind_core/harness/middleware/compaction.py` 实现滑动窗口上下文预算监控与自动摘要折叠中间件，在超长任务中保持模型关键记忆并防止上下文溢出；
3. 在 `atbmind_core/roles/persona.py` 构建 16 种 MBTI 心理学强类型人设模型与 6 维行为规范矩阵（回答风格、冲突应对、规划逻辑等），并实现 `SOUL.md` 动态渲染装配。

**Tech Stack:** Python 3.12+, Pydantic v2, PySide6, pytest, asyncio

**Spec:** [docs/superpowers/specs/2026-10-08-octop-architecture-adoption-design.md](file:///Users/brainzhang/work/aitobox/ATBMind/docs/superpowers/specs/2026-10-08-octop-architecture-adoption-design.md)

## Global Constraints

- 遵循 ATBMind 纯 Python + Pi-Style Micro-Harness 极简设计哲学，坚决不引入 LangChain/LangGraph 等重型框架依赖；
- 保持全部既有 352+ 项测试 100% 通过（零回归）；
- 所有路径检查严格防范跨目录穿越（Zip Slip / Path Traversal）；
- 上下文压缩必须始终保护第一条 System Prompt 与最近 $K$ 轮最新互动消息不被冲刷丢失；
- 测试必须遵循 TDD 规范，先红后绿，每步提交。

## Review Focus

1. **路径越界逃逸防护**：`LocalHostBackend` 面对以 `../` 或绝对路径试图访问根目录之外文件时，必须严格拦截并抛出受控异常，不得读取或覆盖敏感文件；
2. **上下文压缩边缘安全**：当总 token 数低于阈值、或消息轮次不足 $K$ 轮时，`ContextCompactionMiddleware` 必须幂等跳过，不产生任何无谓的 LLM 摘要调用；
3. **单双引号与特殊符号摘要**：压缩历史消息时若包含代码块、Markdown 表格或 JSON 结构体，提取的摘要必须结构完整，不得破坏后续模型解析；
4. **Persona 行为注入一致性**：MBTI 模板渲染进入 System Prompt 时，必须与现有角色预设的职责（Job Role）自然融洽叠加，不得出现人设指令与角色主任务相互矛盾；
5. **异步命令超时兜底**：`BackendProtocol.exec_command` 必须强制支持超时终止（默认 60s），防止外部进程挂起导致整条 Agent Loop 阻塞。

---

### Task 1: 定义 `BackendProtocol` 抽象协议与安全宿主后端 `LocalHostBackend`

**Files:**
- Create: `atbmind_core/harness/backends/__init__.py`
- Create: `atbmind_core/harness/backends/protocol.py`
- Create: `atbmind_core/harness/backends/local.py`
- Create: `tests/test_harness_backends.py`

**Interfaces:**
- Consumes: `pathlib.Path`, `asyncio.subprocess`
- Produces: 
  - `BackendProtocol` (抽象基类 / Protocol):
    - `async def read_file(path: str) -> str`
    - `async def write_file(path: str, content: str) -> None`
    - `async def edit_file(path: str, old_str: str, new_str: str) -> None`
    - `async def list_dir(path: str = ".") -> list[str]`
    - `async def exec_command(cmd: str, timeout: float = 60.0) -> tuple[int, str, str]`
  - `LocalHostBackend(root_dir: str | Path, allow_escape: bool = False)`:
    - 路径自动解析与 `root_dir` 边界校验
  - `MockBackend(files: dict[str, str])`: 内存测试后端

- [ ] **Step 1: 编写失败测试**

在 `tests/test_harness_backends.py` 中编写对 `LocalHostBackend` 正常文件读写、目录列表、命令执行以及越界路径 `../../etc/passwd` 拦截的测试用例。

- [ ] **Step 2: 运行测试验证失败**

Run: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_harness_backends.py -v`  
Expected: FAIL (ModuleNotFoundError 或导入错误)

- [ ] **Step 3: 实现 `BackendProtocol` 与 `LocalHostBackend`**

在 `atbmind_core/harness/backends/protocol.py` 中定义抽象契约，在 `local.py` 中基于 `pathlib.Path.resolve()` 实现越界防护（Path Traversal Guard）及异步子进程命令执行。

- [ ] **Step 4: 运行测试验证通过**

Run: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_harness_backends.py -v`  
Expected: PASS

- [ ] **Step 5: 提交代码**

```bash
git add atbmind_core/harness/backends/ tests/test_harness_backends.py
git commit -m "feat(harness): introduce BackendProtocol and LocalHostBackend with path traversal guard"
```

---

### Task 2: 改造编码与文件工具层全面接入 `BackendProtocol`

**Files:**
- Modify: `atbmind_core/harness/tools/base.py`
- Modify: `atbmind_core/harness/tools/coding.py`
- Modify: `tests/test_harness_backends.py`
- Modify: `tests/test_harness_loop.py`

**Interfaces:**
- Consumes: `BackendProtocol`, `LocalHostBackend`
- Produces: 
  - `AgentTool` 增加 `backend: BackendProtocol | None` 属性及 setter
  - `ReadFileTool`, `WriteFileTool`, `EditFileTool`, `BashTool` 底层统一委托给 `self.backend`

- [ ] **Step 1: 编写失败测试**

在 `tests/test_harness_backends.py` 中添加测试用例：使用 `MockBackend` 实例化 `ReadFileTool` 和 `WriteFileTool`，断言无需触碰磁盘即可完成文件操作，并测试 `BashTool` 在自定义 backend 上的执行。

- [ ] **Step 2: 运行测试验证失败**

Run: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_harness_backends.py -k test_tools_with_backend -v`  
Expected: FAIL

- [ ] **Step 3: 改造现有工具底层执行逻辑**

修改 `atbmind_core/harness/tools/base.py` 与 `coding.py`，使文件与命令行工具优先调用 `self.backend`，若未指定则自动回退到当前工作区的 `LocalHostBackend`。

- [ ] **Step 4: 运行全部相关测试验证通过**

Run: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_harness_backends.py tests/test_harness_loop.py -v`  
Expected: PASS

- [ ] **Step 5: 提交代码**

```bash
git add atbmind_core/harness/tools/ tests/test_harness_backends.py tests/test_harness_loop.py
git commit -m "refactor(harness): adapt coding and bash tools to use BackendProtocol"
```

---

### Task 3: 实现上下文自适应压缩中间件 (`ContextCompactionMiddleware`)

**Files:**
- Create: `atbmind_core/harness/middleware/compaction.py`
- Create: `tests/test_context_compaction.py`
- Modify: `atbmind_core/harness/loop.py`

**Interfaces:**
- Consumes: `AgentMessage`, `Role`
- Produces: 
  - `ContextCompactionMiddleware(max_tokens_budget: int = 4000, keep_recent_turns: int = 3)`:
    - `estimate_tokens(messages: list[AgentMessage]) -> int`
    - `should_compact(messages: list[AgentMessage]) -> bool`
    - `async def compact(messages: list[AgentMessage], summarize_fn: Callable) -> list[AgentMessage]`

- [ ] **Step 1: 编写失败测试**

在 `tests/test_context_compaction.py` 中测试：
1. 消息列表未超过预算时不触发压缩；
2. 超过预算时，保护首条 System Prompt 以及最后 3 轮互动，将其余中间消息折叠为一条包含 `[Conversation Summary: ...]` 的摘要消息；
3. 验证折叠后的总 Token/字符量显著下降。

- [ ] **Step 2: 运行测试验证失败**

Run: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_context_compaction.py -v`  
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: 实现 `ContextCompactionMiddleware` 并在 `loop.py` 挂载**

在 `atbmind_core/harness/middleware/compaction.py` 中实现滑动窗口与摘要折叠算法，在 `agent_loop` 每一轮开始前检查并执行自适应压缩。

- [ ] **Step 4: 运行测试验证通过**

Run: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_context_compaction.py -v`  
Expected: PASS

- [ ] **Step 5: 提交代码**

```bash
git add atbmind_core/harness/middleware/compaction.py atbmind_core/harness/loop.py tests/test_context_compaction.py
git commit -m "feat(harness): add ContextCompactionMiddleware for adaptive history summarization"
```

---

### Task 4: 实现 16 种 MBTI 强类型人格体系与行为规范矩阵

**Files:**
- Create: `atbmind_core/roles/persona.py`
- Create: `tests/test_mbti_persona.py`
- Modify: `atbmind_core/roles/schema.py`
- Modify: `atbmind_core/roles/loader.py`

**Interfaces:**
- Consumes: `RoleDefinition`
- Produces: 
  - `MBTIBehaviorMapping`: 6 维交互行为指引（`answer_style`, `casual_chat`, `conflict_resolution`, `creativity`, `emotion`, `planning`）
  - `MBTIProfile`: 16 种人格定义（INTJ, INTP, ENTJ, ENFP 等）
  - `get_mbti_profile(code: str) -> MBTIProfile | None`
  - `PersonaLoader.render_soul(role: RoleDefinition, mbti: str | None) -> str`

- [ ] **Step 1: 编写失败测试**

在 `tests/test_mbti_persona.py` 中测试：
1. 16 种 MBTI profile 数据结构与中英文描述完备性；
2. 指定 MBTI 代码（如 "INTJ"）时，生成包含系统性思考、不喜闲聊、直击痛点行为约束的 Prompt 骨架；
3. 将 MBTI 配置融入 `RoleDefinition` 并通过 `PersonaLoader` 正确注入角色系统提示词。

- [ ] **Step 2: 运行测试验证失败**

Run: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_mbti_persona.py -v`  
Expected: FAIL

- [ ] **Step 3: 实现人格库与 `PersonaLoader`**

在 `atbmind_core/roles/persona.py` 实现结构化定义，在 `schema.py` 增加 `mbti: Optional[str] = None`，在 `loader.py` 实现动态渲染。

- [ ] **Step 4: 运行测试验证通过**

Run: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_mbti_persona.py -v`  
Expected: PASS

- [ ] **Step 5: 提交代码**

```bash
git add atbmind_core/roles/persona.py atbmind_core/roles/schema.py atbmind_core/roles/loader.py tests/test_mbti_persona.py
git commit -m "feat(roles): add 16 MBTI structured persona profiles and dynamic PersonaLoader"
```

---

### Task 5: 整体集成验证与防回归全量测试

**Files:**
- Test: 全量测试套件 `tests/`

- [ ] **Step 1: 运行全量单元测试与集成测试**

Run: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/`  
Expected: ALL PASS（350+ tests passing, 0 failures）

- [ ] **Step 2: 提交最终集成更新与演进日志**

```bash
git add docs/superpowers/plans/2026-10-08-octop-architecture-adoption-phase2.md
git commit -m "docs: complete implementation plan for octop architecture adoption phase 2"
```
