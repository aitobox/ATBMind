# Implementation Plan: Skill Detail Drawer, Dialogs & Async Workers (Issue #56)

## Overview
Implement the full interactive capability of the ATBMind Skill Manager for the final step of Epic #51:
- Background QThread workers (`SkillImportWorker`, `SkillUpdateWorker`) to run Git imports and updates asynchronously without blocking the UI.
- Modal dialogs (`GitHubImportDialog`, `NewSkillDialog`, `LocalImportDialog`) with real-time URL validation and template preview.
- Slide-out `SkillDetailDrawer` featuring `SKILL.md` rich Markdown preview, tool parameters schema table, `requirements.txt` environment diagnostic, live role binding checkboxes, and action buttons.
- Global `EventBus` pub/sub and `EventBusQtBridge` telemetry.
- Seamless integration in `SkillHubView`.
- Comprehensive automated test suite in `tests/test_skills_e2e_integration.py`.

---

## Detailed Task Breakdown

### Task 1: Background Workers
- **File**: `apps/atbmind_desktop/workers.py`
- **Classes**:
  - `SkillImportWorker(QThread)`:
    - Inputs: `source_url_or_path`, `source_type` ("github" | "local"), `target_scope` ("global" | "project"), `skill_name`, `overwrite`.
    - Signals: `progress(str)`, `finished(bool, str, object)`.
    - Handles safe execution of `manager.import_from_github` or `manager.import_from_local`.
  - `SkillUpdateWorker(QThread)`:
    - Inputs: `skill_name`.
    - Signals: `progress(str)`, `finished(bool, str, object)`.
    - Handles safe execution of `manager.update_skill`.

### Task 2: Import & Scaffolding Modal Dialogs
- **File**: `apps/atbmind_desktop/widgets/skill_dialogs.py`
- **Classes**:
  - `GitHubImportDialog(QDialog)`:
    - Input URL with live validation against `parse_github_url`.
    - Scope radio buttons (`Global` vs `Project`).
    - Overwrite checkbox.
    - Inline progress indicator and message during import.
  - `NewSkillDialog(QDialog)`:
    - Name, description, tags, target scope.
    - Checkbox: "包含 Python 工具代码 (AgentTool)".
    - Real-time template preview (`SKILL.md` and `tools.py`).
  - `LocalImportDialog(QDialog)`:
    - Folder or ZIP file picker.
    - Target scope selection.

### Task 3: Sliding `SkillDetailDrawer`
- **File**: `apps/atbmind_desktop/widgets/skill_drawer.py`
- **Class**: `SkillDetailDrawer(QWidget)`:
  - Header: Title, version badge, source badge, close button.
  - Section 1: `SKILL.md` Markdown viewer (`QTextBrowser`).
  - Section 2: Tools schema inspector table (tool name, description, parameters schema fields).
  - Section 3: Environment diagnostic card (`manager.check_requirements()`).
  - Section 4: Role binding checklist:
    - Lists all roles from `role_registry.list_roles()`.
    - Checkboxes bound to `manager.bind_skill_to_role` and `manager.unbind_skill_from_role`.
  - Section 5: Actions: Update, Open in Finder (`QDesktopServices`), Remove Skill.

### Task 4: Global EventBus & Inspector Telemetry
- **Files**:
  - `atbmind_core/runtime/event_bus.py`: Add `SkillInstalledEvent`, `SkillUpdatedEvent`, `SkillBoundRoleEvent`.
  - `apps/atbmind_desktop/bridge.py`: Add Qt signals and subscriptions for skill events in `EventBusQtBridge`.
  - `apps/atbmind_desktop/main_window.py`: Wire skill signals to refresh Inspector panel.

### Task 5: UI Integration in `SkillHubView`
- **File**: `apps/atbmind_desktop/widgets/skill_hub.py`
- Wire:
  - Clicking `+ 新建技能` opens `NewSkillDialog`.
  - Clicking `⬇️ 导入技能` opens `GitHubImportDialog` (with local option).
  - Clicking `SkillCard` opens `SkillDetailDrawer`.
  - Clicking `Update` launches `SkillUpdateWorker`.

### Task 6: Unit & Integration Tests
- **File**: `tests/test_skills_e2e_integration.py`
- Test cases covering dialogs, drawer, role binding, workers, and events.

### Task 7: Full Regression Pass
- Run complete test suite: `PYTHONPATH=. conda run -n ATBMind python -m pytest tests/`

### Task 8: `grill-me` Audit & Review Transition
- Run audit and transition state to `reviewing`.
