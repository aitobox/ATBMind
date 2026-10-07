# RobotRole & Skill 架构升级实施计划 (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 彻底废除旧的 Plugin 插件体系，基于 Harness Loop 内核建立标准化的 RobotRole 专家角色与 Skill 技能体系，支持开源生态导入，完成 Draw 专家迁移与桌面端集成，并更新 README。

**Architecture:** 采用“Harness Loop 内核 -> RobotRole 角色层 -> Skill 技能层 -> RobotTeam 团队编排”四层架构。主协调员（Coordinator）作为与用户的直接交互接口，通过元工具 `delegate_task` 启动专家的独立子循环（Sub-Harness Loop），实现上下文隔离与专业任务执行闭环。

**Tech Stack:** Python 3.12, PySide6, Pydantic V2, Pytest, PyYAML.

**Spec:** [`docs/superpowers/specs/2026-10-07-robotrole-skill-architecture-design.md`](file:///Users/brainzhang/work/aitobox/ATBMind/docs/superpowers/specs/2026-10-07-robotrole-skill-architecture-design.md)

## Global Constraints

- 运行与测试环境必须在 conda 环境 `ATBMind` 下执行 (`conda run -n ATBMind`)。
- 测试验证命令必须通过：`PYTHONPATH=. conda run -n ATBMind python -m pytest tests/`。
- 绝不引入重型外部 agent 编排框架依赖（如 langchain/crewai），维持零外部 agent 依赖的极简内核。
- 保证原有画图能力（生图、修图、模板、风格参数）100% 迁移与可用。

## Review Focus

1. **子循环异常隔离**：子专家在执行工具报错或超时时，不能导致主协调员崩溃，错误必须包装为结构化 `ToolResult`。
2. **Steering 与取消传递**：用户在界面点击“停止”时，`cancellation_token` 必须能即时中断正在运行的子专家循环。
3. **SKILL.md 兼容性**：第三方开源技能库的 `SKILL.md` 若缺少某些非核心字段，解析器必须容错降级，不能崩溃。
4. **上下文防污染**：子专家的中间思考过程和工具重试信息不得混入主会话的 `messages` 历史，只回传最终摘要与成果。
5. **旧数据平滑读取**：SQLite 数据库中原 `plugin_id` 历史记录在加载时能平滑映射，不报错。

---

### Task 1: 存储模型解耦与迁移 (Decouple Storage Models from Plugins)

**Files:**
- Create: `atbmind_core/storage/schemas.py`
- Modify: `atbmind_core/storage/session_store.py:1-25`
- Modify: `atbmind_core/harness/session.py:1-35`
- Modify: `apps/atbmind_desktop/state.py:1-20`
- Modify: `apps/atbmind_desktop/widgets/sidebar.py:1-20`
- Modify: `apps/atbmind_desktop/widgets/chat_stream.py:1-20`
- Test: `tests/test_session_store.py`

**Interfaces:**
- Consumes: Pydantic v2 `BaseModel`
- Produces: `atbmind_core.storage.schemas.MessageRecord`, `atbmind_core.storage.schemas.SessionRecord`

- [ ] **Step 1: Write failing test in `tests/test_storage_schemas.py`**

```python
from atbmind_core.storage.schemas import MessageRecord, SessionRecord

def test_storage_schemas_import_and_defaults():
    msg = MessageRecord(session_id="s1", role="user", content="hello")
    assert msg.session_id == "s1"
    assert msg.role == "user"
    sess = SessionRecord(session_id="s1", title="Title")
    assert sess.session_id == "s1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n ATBMind python -m pytest tests/test_storage_schemas.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'atbmind_core.storage.schemas'`

- [ ] **Step 3: Implement `atbmind_core/storage/schemas.py` and update imports**

Define `MessageRecord` and `SessionRecord` in `atbmind_core/storage/schemas.py`, then update imports across `session_store.py`, `harness/session.py`, `apps/atbmind_desktop/state.py`, `sidebar.py`, and `chat_stream.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n ATBMind python -m pytest tests/test_storage_schemas.py tests/test_session_store.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add atbmind_core/storage/schemas.py atbmind_core/storage/session_store.py atbmind_core/harness/session.py apps/atbmind_desktop/ tests/test_storage_schemas.py
git commit -m "refactor(storage): decouple MessageRecord and SessionRecord from plugins"
```

---

### Task 2: 技能模块核心数据结构与解析器 (Skill Core & Loader)

**Files:**
- Create: `atbmind_core/skills/__init__.py`
- Create: `atbmind_core/skills/schema.py`
- Create: `atbmind_core/skills/loader.py`
- Create: `atbmind_core/skills/registry.py`
- Test: `tests/test_skills.py`

**Interfaces:**
- Consumes: `atbmind_core.harness.tools.base.AgentTool`
- Produces:
  - `SkillMetadata(name, description, version, tags)`
  - `Skill(metadata, domain_prompt, tools, skill_dir)`
  - `SkillLoader.load_from_dir(path: Path) -> Skill`
  - `SkillRegistry.scan_directory(dir_path: Path) -> int`
  - `SkillRegistry.get_skill(name: str) -> Skill`

- [ ] **Step 1: Write failing test in `tests/test_skills.py`**

```python
from pathlib import Path
from atbmind_core.skills.loader import SkillLoader
from atbmind_core.skills.registry import SkillRegistry

def test_load_skill_from_markdown(tmp_path: Path):
    skill_dir = tmp_path / "mock_skill"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        "---\nname: mock_skill\ndescription: Mock Description\nversion: 1.0.0\ntags: ['test']\n---\n# Rules\nAlways return mock.",
        encoding="utf-8"
    )
    tools_py = skill_dir / "tools.py"
    tools_py.write_text(
        "from atbmind_core.harness.tools.base import AgentTool, ToolResult\n"
        "from pydantic import BaseModel\n"
        "class MockInput(BaseModel):\n    arg: str = ''\n"
        "class MockTool(AgentTool):\n"
        "    name = 'mock_tool'\n"
        "    description = 'mock'\n"
        "    parameters_schema = MockInput\n"
        "    async def execute(self, args, ctx=None): return ToolResult('ok')\n",
        encoding="utf-8"
    )

    skill = SkillLoader.load_from_dir(skill_dir)
    assert skill.metadata.name == "mock_skill"
    assert skill.metadata.description == "Mock Description"
    assert "Always return mock." in skill.domain_prompt
    assert len(skill.tools) == 1
    assert skill.tools[0].name == "mock_tool"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n ATBMind python -m pytest tests/test_skills.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'atbmind_core.skills'`

- [ ] **Step 3: Implement `atbmind_core/skills/`**

- `schema.py`: Define `SkillMetadata` and `Skill` (holding metadata, domain_prompt, tools list, directory path).
- `loader.py`: Parse YAML frontmatter + Markdown body using regex/pyyaml; dynamically load `tools.py` via `importlib.util.spec_from_file_location` and collect subclasses of `AgentTool`.
- `registry.py`: `SkillRegistry` with singleton helper `get_skill_registry()`, scanning directories for `SKILL.md` subdirectories.

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n ATBMind python -m pytest tests/test_skills.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add atbmind_core/skills/ tests/test_skills.py
git commit -m "feat(skills): implement Skill schema, SKILL.md loader and registry"
```

---

### Task 3: 角色模块数据结构与加载器 (RobotRole Core & Registry)

**Files:**
- Create: `atbmind_core/roles/__init__.py`
- Create: `atbmind_core/roles/schema.py`
- Create: `atbmind_core/roles/loader.py`
- Create: `atbmind_core/roles/registry.py`
- Test: `tests/test_roles.py`

**Interfaces:**
- Consumes: `atbmind_core.skills.schema.Skill`, `SkillRegistry`
- Produces:
  - `RobotRole(role_id, name, description, personality, system_prompt, skills, model, temperature)`
  - `RobotRole.build_system_prompt(loaded_skills: Dict[str, Skill]) -> str`
  - `RobotRole.collect_tools(loaded_skills: Dict[str, Skill]) -> List[AgentTool]`
  - `RoleRegistry.scan_directory(dir_path: Path) -> int`
  - `RoleRegistry.get_role(role_id: str) -> RobotRole`

- [ ] **Step 1: Write failing test in `tests/test_roles.py`**

```python
from pathlib import Path
from atbmind_core.roles.loader import RoleLoader
from atbmind_core.skills.schema import Skill, SkillMetadata

def test_load_role_and_build_system_prompt(tmp_path: Path):
    role_dir = tmp_path / "test_role"
    role_dir.mkdir()
    role_yaml = role_dir / "role.yaml"
    role_yaml.write_text(
        "role_id: test_role\n"
        "name: 测试专家\n"
        "description: 测试描述\n"
        "personality: 幽默风趣\n"
        "system_prompt: 你是测试助手\n"
        "skills:\n  - mock_skill\n",
        encoding="utf-8"
    )
    role = RoleLoader.load_from_dir(role_dir)
    assert role.role_id == "test_role"
    assert role.name == "测试专家"

    mock_skill = Skill(
        metadata=SkillMetadata(name="mock_skill", description="desc"),
        domain_prompt="请按照测试规范行事",
        tools=[],
        skill_dir=str(tmp_path)
    )
    prompt = role.build_system_prompt({"mock_skill": mock_skill})
    assert "幽默风趣" in prompt
    assert "请按照测试规范行事" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n ATBMind python -m pytest tests/test_roles.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'atbmind_core.roles'`

- [ ] **Step 3: Implement `atbmind_core/roles/`**

- `schema.py`: Define `RobotRole` with `build_system_prompt` and `collect_tools`.
- `loader.py`: Load `role.yaml` via PyYAML into `RobotRole`.
- `registry.py`: `RoleRegistry` to scan directory and retrieve roles.

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n ATBMind python -m pytest tests/test_roles.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add atbmind_core/roles/ tests/test_roles.py
git commit -m "feat(roles): implement RobotRole schema, loader, and registry"
```

---

### Task 4: 团队编排与 Subagent 派发执行器 (RobotTeam & Subagent Delegation)

**Files:**
- Create: `atbmind_core/roles/team.py`
- Create: `atbmind_core/roles/delegation.py`
- Test: `tests/test_roles_delegation.py`

**Interfaces:**
- Consumes: `RobotRole`, `SkillRegistry`, `RoleRegistry`, `atbmind_core.harness.loop.agent_loop`
- Produces:
  - `RobotTeam(leader_role_id: str, role_registry: RoleRegistry, skill_registry: SkillRegistry)`
  - `DelegateTaskTool(team: RobotTeam, stream_client: Any)`
  - `RobotTeam.create_coordinator_session(session_id: str, stream_client: Any) -> AgentSession`

- [ ] **Step 1: Write failing test in `tests/test_roles_delegation.py`**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from atbmind_core.roles.team import RobotTeam
from atbmind_core.roles.schema import RobotRole
from atbmind_core.skills.schema import Skill, SkillMetadata
from atbmind_core.harness.types import AgentEvent, AgentEventType, AgentMessage, Role

@pytest.mark.anyio
async def test_delegate_task_execution():
    team = MagicMock(spec=RobotTeam)
    specialist = RobotRole(
        role_id="specialist",
        name="专员",
        description="专业执行",
        system_prompt="专员提示词",
        skills=[],
    )
    team.get_role.return_value = specialist
    team.collect_role_tools.return_value = []
    
    mock_stream_client = MagicMock()
    # Mock stream_chat returning an assistant reply
    async def mock_stream_chat(*args, **kwargs):
        yield AgentEvent(AgentEventType.MESSAGE_START, {"message": AgentMessage(role=Role.ASSISTANT)})
        yield AgentEvent(AgentEventType.MESSAGE_DELTA, {"delta": "任务已完成"})
        yield AgentEvent(AgentEventType.MESSAGE_END, {"message": AgentMessage(role=Role.ASSISTANT, content="任务已完成")})
    mock_stream_client.stream_chat = mock_stream_chat

    from atbmind_core.roles.delegation import DelegateTaskTool
    tool = DelegateTaskTool(team=team, stream_client=mock_stream_client)
    res = await tool.execute({"role_id": "specialist", "task_description": "请处理数据"})
    assert not res.is_error
    assert "任务已完成" in res.content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n ATBMind python -m pytest tests/test_roles_delegation.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'atbmind_core.roles.team'`

- [ ] **Step 3: Implement `team.py` and `delegation.py`**

- `delegation.py`: Implement `DelegateTaskTool(AgentTool)` that extracts target role from team, builds child `AgentContext`, runs `agent_loop(...)`, captures intermediate events (tagging them with role metadata), and returns final response as `ToolResult`.
- `team.py`: Implement `RobotTeam` managing member roles, providing coordinator system prompt injection with team member roster, and registering `DelegateTaskTool`.

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n ATBMind python -m pytest tests/test_roles_delegation.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add atbmind_core/roles/team.py atbmind_core/roles/delegation.py tests/test_roles_delegation.py
git commit -m "feat(roles): implement RobotTeam and DelegateTaskTool subagent executor"
```

---

### Task 5: 迁移创建标准技能库与角色库 (`skills/` & `roles/`)

**Files:**
- Create: `skills/image_generation/SKILL.md`
- Create: `skills/image_generation/tools.py`
- Create: `roles/coordinator/role.yaml`
- Create: `roles/draw_expert/role.yaml`
- Test: `tests/test_draw_robot_role.py`

**Interfaces:**
- Consumes: `plugins.draw.adapters.base.create_image_adapter`
- Produces:
  - Official `skills/image_generation/` package
  - Official `roles/coordinator/` and `roles/draw_expert/` definitions

- [ ] **Step 1: Write integration test `tests/test_draw_robot_role.py`**

```python
import pytest
from pathlib import Path
from atbmind_core.skills.registry import SkillRegistry
from atbmind_core.roles.registry import RoleRegistry
from atbmind_core.roles.team import RobotTeam

@pytest.mark.anyio
async def test_draw_expert_role_integration():
    skill_reg = SkillRegistry()
    skill_reg.scan_directory(Path("skills"))
    assert "image_generation" in skill_reg.list_skills()

    role_reg = RoleRegistry(skill_registry=skill_reg)
    role_reg.scan_directory(Path("roles"))
    assert "draw_expert" in role_reg.list_roles()
    assert "coordinator" in role_reg.list_roles()

    draw_role = role_reg.get_role("draw_expert")
    tools = draw_role.collect_tools(skill_reg.get_all_skills())
    tool_names = [t.name for t in tools]
    assert "generate_image" in tool_names
    assert "refine_image" in tool_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n ATBMind python -m pytest tests/test_draw_robot_role.py -v`  
Expected: FAIL because `skills/` and `roles/` do not exist yet.

- [ ] **Step 3: Implement `skills/image_generation/` and `roles/`**

- Move `GenerateImageTool`, `RefineImageTool`, and `SearchTemplatesTool` into `skills/image_generation/tools.py`.
- Create `skills/image_generation/SKILL.md` incorporating portrait retouching guidelines and style prompts.
- Create `roles/coordinator/role.yaml` and `roles/draw_expert/role.yaml`.

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n ATBMind python -m pytest tests/test_draw_robot_role.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/ roles/ tests/test_draw_robot_role.py
git commit -m "feat(skills,roles): add image_generation skill, coordinator and draw_expert roles"
```

---

### Task 6: 桌面端 GenerationWorker 重构与角色团队接入 (Desktop Worker Refactor)

**Files:**
- Modify: `apps/atbmind_desktop/workers.py`
- Modify: `apps/atbmind_desktop/main_window.py`
- Test: `tests/test_atbmind_desktop.py`
- Test: `tests/test_desktop_workers_roles.py`

**Interfaces:**
- Consumes: `RobotTeam`, `atbmind_core.storage.schemas.SessionRecord`
- Produces: `GenerationWorker` running `RobotTeam` coordinator session, emitting `tool_started`, `tool_finished`, `token_received`, `finished`.

- [ ] **Step 1: Write failing test in `tests/test_desktop_workers_roles.py`**

```python
from unittest.mock import MagicMock
from apps.atbmind_desktop.workers import GenerationWorker

def test_generation_worker_initialization_with_roles():
    worker = GenerationWorker(
        session_id="test_sess",
        user_prompt="帮我画一张人像",
        use_harness=True,
    )
    assert worker.session_id == "test_sess"
    assert not hasattr(worker, "active_plugin_id") or worker.active_plugin_id is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n ATBMind python -m pytest tests/test_desktop_workers_roles.py -v`  
Expected: FAIL due to existing active_plugin_id assumptions.

- [ ] **Step 3: Refactor `apps/atbmind_desktop/workers.py` and `main_window.py`**

- In `GenerationWorker`: Replace plugin-based execution branches with `RobotTeam` coordination.
- In `MainWindow`: Replace plugin selection state with role/team context steering.
- Ensure all GUI signals (`tool_started`, `tool_finished`, `finished`, `token_received`) are emitted properly.

- [ ] **Step 4: Run desktop tests to verify they pass**

Run: `conda run -n ATBMind python -m pytest tests/test_desktop_workers_roles.py tests/test_atbmind_desktop.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/atbmind_desktop/ tests/test_desktop_workers_roles.py tests/test_atbmind_desktop.py
git commit -m "refactor(desktop): switch GenerationWorker to RobotTeam architecture"
```

---

### Task 7: 清理旧插件系统与废弃代码 (Retire Legacy Plugin System)

**Files:**
- Delete: `atbmind_core/plugins/` (or replace with deprecated wrappers if needed)
- Delete: `atbmind_core/engine/completer.py`, `planner.py`, `dispatcher.py`
- Clean/Update: `tests/test_plugin_*.py`, `tests/test_planner.py`, `tests/test_dispatcher.py`

**Interfaces:**
- Consumes: none
- Produces: Clean codebase without `Plugin` remnants

- [ ] **Step 1: Verify all replacement tests are in place**

Ensure `tests/test_skills.py`, `tests/test_roles.py`, `tests/test_roles_delegation.py`, `tests/test_draw_robot_role.py` cover all functionalities.

- [ ] **Step 2: Remove obsolete plugin files and update legacy test files**

Remove `atbmind_core/plugins/` and old planner/dispatcher files. Update or remove legacy plugin unit tests that test deleted classes.

- [ ] **Step 3: Run full pytest suite across entire project**

Run: `conda run -n ATBMind python -m pytest tests/`  
Expected: All tests PASS with zero errors.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor: retire legacy plugin SPI and engine state machines"
```

---

### Task 8: 更新 README.md 项目设计架构与理念 (Update README Documentation)

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Draft the README update**

Add new architectural sections:
1. **核心理念**：从插件系统全面升级为以 Harness Loop 为底座、以专才角色（RobotRole）为载体、以模块化兼容开源（Skill）为能力的现代智能体。
2. **架构分层图**：展示 Harness Loop -> RobotRole Team -> Skills 分层。
3. **开源技能导入与扩展指南**：详细说明如何将 GitHub 开源 `SKILL.md` 放入 `skills/` 目录，以及如何编写 `roles/<name>/role.yaml` 组建专属专家团队。

- [ ] **Step 2: Apply changes to `README.md`**

Update `README.md` with idiomatic markdown, clear diagrams, and usage examples.

- [ ] **Step 3: Verify documentation integrity and links**

Ensure all markdown links and code snippets are accurate and clean.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: update README with RobotRole and Skill architecture documentation"
```
