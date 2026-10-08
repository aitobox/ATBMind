# Skill System Runtime Pipeline & Desktop UX Refinement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix critical runtime disconnections in Skill Manager (global skill discovery in GenerationWorker, disabled state filtering in RobotRole prompt/tools, frontmatter persistence), convert synchronous Git update checks into a non-blocking background QThread, and enhance SkillDetailDrawer ergonomics (ESC key close, one-click pip dependency installation).

**Architecture:**
- **Runtime Core:** Unify skill discovery in `GenerationWorker` via `SkillManager.get_instance().discover_all()`, filter out disabled skills in `RobotRole.build_system_prompt()` and `RobotRole.collect_tools()`, and fix frontmatter parsing in `SkillManager.set_skill_enabled()` to reliably inject `enabled:` if missing.
- **Async Workers:** Add `SkillCheckUpdatesWorker` and `SkillPipInstallWorker` in `apps/atbmind_desktop/workers.py` inheriting `QThread` to decouple network/IO operations from the Qt GUI thread.
- **Drawer UX:** Add ESC key shortcut handling for drawer closing, disable update checks on local non-git skills, and provide a one-click "📦 一键安装缺失依赖" button powered by `SkillPipInstallWorker`.

**Tech Stack:** Python 3.12, PySide6, Pydantic, pytest, Git CLI, Pip.

**Spec:** Aligned via `/grill-me` interactive design interview on 2026-10-08.

## Global Constraints

- Dev environment: `conda activate ATBMind`, Python 3.12, PySide6.
- Run tests with: `PYTHONPATH=. conda run -n ATBMind python -m pytest tests/`
- Zero regressions on existing 328 unit and integration tests.
- Maintain Apple HIG desktop styling tokens (`ThemeColors`, `ThemeFonts`, `get_apple_icon`).

## Review Focus

1. `SKILL.md` with no initial `enabled:` frontmatter key must persist correctly when toggled off and on.
2. `RobotRole` with bound skills must not expose domain prompts or tools from disabled skills to LLM context.
3. `GenerationWorker` must discover both project `./skills` and global `~/.atbmind/skills`.
4. `check_updates()` in GUI must never freeze or block the Qt event loop.
5. `ESC` key press must dismiss the detail drawer without raising uncaught exceptions when focused in different widgets.

---

### Task 1: Runtime Skills Pipeline & Enabled State Filtering

**Files:**
- Modify: `atbmind_core/roles/schema.py:43-64`
- Modify: `atbmind_core/skills/manager.py:840-858`
- Test: `tests/test_skills_manager.py`, `tests/test_roles.py`

**Interfaces:**
- Consumes: `Skill.metadata.enabled: bool`, `SkillManager.set_skill_enabled(name: str, enabled: bool)`
- Produces: Reliable frontmatter persistence on disk; strict exclusion of disabled skills from `RobotRole.build_system_prompt` and `RobotRole.collect_tools`.

- [ ] **Step 1: Write failing tests for frontmatter injection and disabled skill filtering**

In `tests/test_skills_manager.py`:
```python
def test_set_skill_enabled_injects_field_if_missing(tmp_path):
    # Create SKILL.md without enabled: line
    # Call manager.set_skill_enabled(..., False)
    # Assert SKILL.md contains enabled: false
```
In `tests/test_roles.py`:
```python
def test_robot_role_excludes_disabled_skills():
    # Create role with 2 skills (one enabled=True, one enabled=False)
    # Assert build_system_prompt only contains enabled skill domain prompt
    # Assert collect_tools only contains enabled skill tools
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. conda run -n ATBMind python -m pytest tests/test_skills_manager.py -k test_set_skill_enabled_injects_field_if_missing tests/test_roles.py -k test_robot_role_excludes_disabled_skills -v`
Expected: FAIL

- [ ] **Step 3: Implement fix in `atbmind_core/roles/schema.py` and `atbmind_core/skills/manager.py`**

In `atbmind_core/roles/schema.py`:
```python
# In build_system_prompt():
for s_name in self.skills:
    skill = loaded_skills.get(s_name)
    if skill and getattr(skill.metadata, "enabled", True) and skill.domain_prompt:
        domain_guides.append(f"### Skill 指南 [{s_name}]\n{skill.domain_prompt.strip()}")

# In collect_tools():
for s_name in self.skills:
    skill = loaded_skills.get(s_name)
    if skill and getattr(skill.metadata, "enabled", True) and skill.tools:
        tools.extend(skill.tools)
```

In `atbmind_core/skills/manager.py`:
Update `set_skill_enabled` to check if `^enabled:\s*` exists; if not, find the closing `---` in frontmatter and insert `enabled: {true/false}\n` before it. If no frontmatter block exists, prepend frontmatter.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. conda run -n ATBMind python -m pytest tests/test_skills_manager.py -k test_set_skill_enabled_injects_field_if_missing tests/test_roles.py -k test_robot_role_excludes_disabled_skills -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add atbmind_core/roles/schema.py atbmind_core/skills/manager.py tests/test_skills_manager.py tests/test_roles.py
git commit -m "fix(skills): filter disabled skills in RobotRole and reliably persist frontmatter enabled state"
```

---

### Task 2: GenerationWorker Global Skill Discovery Integration

**Files:**
- Modify: `apps/atbmind_desktop/workers.py:375-405`
- Modify: `apps/atbmind_desktop/main_window.py:700-720`
- Test: `tests/test_desktop_workers_roles.py`

**Interfaces:**
- Consumes: `SkillManager.get_instance().discover_all() -> SkillRegistry`
- Produces: `GenerationWorker` uses `SkillManager.get_instance().skill_registry` for `RoleRegistry` and `RobotTeam`, ensuring global skills (`~/.atbmind/skills`) are fully available.

- [ ] **Step 1: Write failing test in `tests/test_desktop_workers_roles.py`**

```python
def test_generation_worker_discovers_skills_via_skill_manager():
    # Verify GenerationWorker accepts optional skill_manager or uses SkillManager.get_instance().discover_all()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. conda run -n ATBMind python -m pytest tests/test_desktop_workers_roles.py -k test_generation_worker_discovers_skills_via_skill_manager -v`
Expected: FAIL

- [ ] **Step 3: Implement SkillManager resolution in `GenerationWorker`**

In `apps/atbmind_desktop/workers.py`:
- Accept `skill_manager: Optional[SkillManager] = None` in `GenerationWorker.__init__`.
- In `_async_harness_run`:
  ```python
  from atbmind_core.skills.manager import SkillManager
  mgr = self.skill_manager or SkillManager.get_instance()
  mgr.discover_all()
  skill_reg = mgr.skill_registry
  ```
- In `apps/atbmind_desktop/main_window.py`: pass `skill_manager=getattr(self, "skill_manager", None)` when constructing `GenerationWorker`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. conda run -n ATBMind python -m pytest tests/test_desktop_workers_roles.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/atbmind_desktop/workers.py apps/atbmind_desktop/main_window.py tests/test_desktop_workers_roles.py
git commit -m "feat(runtime): integrate SkillManager discovery into GenerationWorker for global and local skills"
```

---

### Task 3: Asynchronous Git Update Checker (`SkillCheckUpdatesWorker`)

**Files:**
- Modify: `apps/atbmind_desktop/workers.py:700-740`
- Modify: `apps/atbmind_desktop/widgets/skill_hub.py:458-480, 940-955`
- Test: `tests/test_skills_ui.py`

**Interfaces:**
- Consumes: `SkillManager.check_updates() -> Dict[str, bool]`
- Produces: `SkillCheckUpdatesWorker(QThread)` with `finished = Signal(dict)` signal; non-blocking button state in `SkillHubView`.

- [ ] **Step 1: Write failing test in `tests/test_skills_ui.py`**

```python
def test_skill_check_updates_worker_async(qapp):
    # Mock skill_manager.check_updates
    # Run SkillCheckUpdatesWorker, verify finished signal emits update results dict
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. conda run -n ATBMind python -m pytest tests/test_skills_ui.py -k test_skill_check_updates_worker_async -v`
Expected: FAIL

- [ ] **Step 3: Implement `SkillCheckUpdatesWorker` and integrate into `SkillHubView`**

In `apps/atbmind_desktop/workers.py`:
```python
class SkillCheckUpdatesWorker(QThread):
    progress = Signal(str)
    finished = Signal(dict)  # result mapping {skill_name: has_update}

    def __init__(self, skill_manager=None, parent=None):
        super().__init__(parent)
        self.skill_manager = skill_manager or SkillManager.get_instance()

    def run(self):
        try:
            res = self.skill_manager.check_updates()
            self.finished.emit(res)
        except Exception as e:
            logger.error("SkillCheckUpdatesWorker error: %s", e)
            self.finished.emit({})
```
In `apps/atbmind_desktop/widgets/skill_hub.py`:
- Refactor `check_updates()` to spawn `SkillCheckUpdatesWorker`.
- During run: `btn_check_updates.setEnabled(False)`, `btn_check_updates.setText("🔄 检查中...")`.
- On finish: restore button text and enabled state, call `self.load_skills()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. conda run -n ATBMind python -m pytest tests/test_skills_ui.py -k test_skill_check_updates_worker_async -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/atbmind_desktop/workers.py apps/atbmind_desktop/widgets/skill_hub.py tests/test_skills_ui.py
git commit -m "feat(ui): add asynchronous SkillCheckUpdatesWorker to prevent GUI thread blocking"
```

---

### Task 4: SkillDetailDrawer Ergonomics & One-Click Dependency Installer

**Files:**
- Modify: `apps/atbmind_desktop/workers.py:730-770`
- Modify: `apps/atbmind_desktop/widgets/skill_drawer.py:455-520`
- Modify: `apps/atbmind_desktop/widgets/skill_hub.py:840-860`
- Test: `tests/test_skills_e2e_integration.py`

**Interfaces:**
- Consumes: `SkillManager.check_requirements(skill_name)`
- Produces: `SkillPipInstallWorker(QThread)`, "一键安装依赖" button in drawer, ESC key drawer close handling.

- [ ] **Step 1: Write failing test in `tests/test_skills_e2e_integration.py`**

```python
def test_skill_drawer_one_click_install_and_esc_close(qapp, tmp_path):
    # Verify btn_install_req created when missing deps exist
    # Verify keyPressEvent with Qt.Key_Escape emits closed signal
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. conda run -n ATBMind python -m pytest tests/test_skills_e2e_integration.py -k test_skill_drawer_one_click_install_and_esc_close -v`
Expected: FAIL

- [ ] **Step 3: Implement `SkillPipInstallWorker` and drawer enhancements**

In `apps/atbmind_desktop/workers.py`:
```python
class SkillPipInstallWorker(QThread):
    progress = Signal(str)
    finished = Signal(bool, str)  # success, message

    def __init__(self, packages: list[str], parent=None):
        super().__init__(parent)
        self.packages = packages

    def run(self):
        import subprocess, sys
        cmd = [sys.executable, "-m", "pip", "install", *self.packages]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if res.returncode == 0:
                self.finished.emit(True, "安装成功")
            else:
                self.finished.emit(False, res.stderr or "安装失败")
        except Exception as e:
            self.finished.emit(False, str(e))
```
In `apps/atbmind_desktop/widgets/skill_drawer.py`:
- In `_render_requirements`: if `missing` list is non-empty, add `self.btn_install_deps = QPushButton("📦 一键安装缺失依赖", self.env_container)`.
- Connect button to launch `SkillPipInstallWorker(missing)`. On finished, refresh `self._render_requirements(skill_name)`.
- Add `keyPressEvent(event: QKeyEvent)`: if `event.key() == Qt.Key.Key_Escape`, emit `self.closed.emit()`.
- In `_render_actions`: disable or hide "检查更新" action if skill has no remote repository (`source_type != "github" and not repo_url`).
In `apps/atbmind_desktop/widgets/skill_hub.py`:
- Add `keyPressEvent(event: QKeyEvent)`: if `event.key() == Qt.Key.Key_Escape` and `self.drawer.isVisible()`, call `self.close_skill_drawer()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. conda run -n ATBMind python -m pytest tests/test_skills_e2e_integration.py -k test_skill_drawer_one_click_install_and_esc_close -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/atbmind_desktop/workers.py apps/atbmind_desktop/widgets/skill_drawer.py apps/atbmind_desktop/widgets/skill_hub.py tests/test_skills_e2e_integration.py
git commit -m "feat(ui): add one-click dependency installer and ESC key drawer close handling"
```

---

### Task 5: Full Regression Pass & Verification

**Files:**
- Test: all `tests/`

- [ ] **Step 1: Run complete test suite**

Run: `PYTHONPATH=. conda run -n ATBMind python -m pytest tests/ -v`
Expected: All tests pass (>= 332 tests, 0 failures).

- [ ] **Step 2: Commit final refinements if needed**
