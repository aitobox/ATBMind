# Technical Specification: Skill Detail Drawer, Dialogs & Async Workers (Issue #56)

## 1. Context & Objectives

- **Issue**: [#56 [skill-mgr] 实现技能详情抽屉、导入向导弹窗与异步 Worker 全流程集成](https://github.com/aitobox/ATBMind/issues/56)
- **Parent Epic**: [#51 [Epic] ATBMind Skill Manager: 集成集中管理、更新、新建、本地与 GitHub 仓库技能导入系统](https://github.com/aitobox/ATBMind/issues/51)
- **Sequence**: Step 5 of 5 (Final Step of Epic #51)
- **Depends On**: #55
- **Framework**: PySide6, Apple HIG Design tokens (`apps/atbmind_desktop/theme.py`)

### Problem Statement
With the `SkillHubView` workbench and card grid implemented in Issue #55, users now need:
1. A rich sliding detail view (`SkillDetailDrawer`) to read `SKILL.md` markdown documentation, inspect exported `AgentTool` schemas, diagnose environment dependencies (`requirements.txt`), dynamically bind/unbind expert roles with immediate persistence, and access management actions (Finder reveal, remove, update).
2. Native Apple HIG modal dialogs (`GitHubImportDialog`, `NewSkillDialog`, `LocalImportDialog`) with real-time validation and preview.
3. Background asynchronous execution (`SkillImportWorker`, `SkillUpdateWorker` via `QThread`) with non-blocking progress feedback to eliminate UI freezes during git clones and sparse checkouts.
4. Global `EventBus` pub/sub synchronization (`SkillInstalledEvent`, `SkillUpdatedEvent`, `SkillBoundRoleEvent`) to update `InspectorPanel` and the desktop UI in real time.

---

## 2. Architecture & Components

```
+----------------------------------------------------------------------------------------------------+
| ATBMind Desktop WorkStreamArea                                                                    |
|                                                                                                    |
| +-------------------------------------------------------+ +--------------------------------------+ |
| | SkillHubView                                          | | SkillDetailDrawer                    | |
| |                                                       | |                                      | |
| |  [Header Toolbar: Search, Pills, +New, ⬇️Import, ...]  | | [Header: Title, Version, Badges, ✕]  | |
| |                                                       | |                                      | |
| |  [SkillCard Grid]                                     | | 📄 SKILL.md Markdown Preview         | |
| |   - Card 1 ---- click --------------------------------->| ⚡ Exported Tools Schema Table        | |
| |   - Card 2                                            | | 📦 Environment Diagnostic Card       | |
| |                                                       | | 🤖 Role Binding Checkbox Matrix      | |
| |  [Modals: NewSkillDialog / GitHubImportDialog]        | | 🛠️ Actions: [Update][Finder][Remove]  | |
| +-------------------------------------------------------+ +--------------------------------------+ |
|                                                                                                    |
| Background Async Layer:                                                                            |
|  - SkillImportWorker (QThread): progress -> dialog/status, finished -> reload                     |
|  - SkillUpdateWorker (QThread): progress -> card/status, finished -> hot reload                    |
|  - EventBus (AsyncEventBus) -> EventBusQtBridge -> InspectorPanel & Main Window                    |
+----------------------------------------------------------------------------------------------------+
```

### 2.1 Asynchronous Workers (`apps/atbmind_desktop/workers.py`)
- **`SkillImportWorker(QThread)`**:
  - Signals: `progress = Signal(str)`, `finished = Signal(bool, str, object)`.
  - Performs `import_from_github` or `import_from_local` in background thread.
  - Safely emits status messages at each step.
- **`SkillUpdateWorker(QThread)`**:
  - Signals: `progress = Signal(str)`, `finished = Signal(bool, str, object)`.
  - Performs `update_skill` with snapshot backup in background thread.

### 2.2 Modal Dialogs (`apps/atbmind_desktop/widgets/skill_dialogs.py`)
- **`GitHubImportDialog(QDialog)`**:
  - Real-time GitHub URL parser validator: highlights owner/repo, branch, subpath.
  - Scope radio options: Global (`~/.atbmind/skills`) vs Project (`./skills`).
  - Overwrite option checkbox.
  - Inline progress banner and spinner during worker import.
- **`NewSkillDialog(QDialog)`**:
  - Skill name, description, tags inputs.
  - Option to include `tools.py` AgentTool scaffold.
  - Scope radio options: Global vs Project.
  - Instant live template preview tab.
- **`LocalImportDialog(QDialog)`**:
  - File picker for local folder or `.zip` archive.
  - Scope selection and name override.

### 2.3 Sliding Drawer (`apps/atbmind_desktop/widgets/skill_drawer.py`)
- **`SkillDetailDrawer(QWidget)`**:
  - Apple HIG glassmorphic sliding panel (width 440px).
  - Sections:
    1. Header: Name, version, source, close `[✕]` button.
    2. SKILL.md Markdown Viewer: `QTextBrowser` with Markdown support.
    3. Tool Schema Inspector: Accordion/table listing parameters schema and documentation.
    4. Environment Diagnostic: Displays `requirements.txt` packages (installed checkmark vs missing alert).
    5. Role Binding Checkbox Matrix: Lists all `RobotRole`s from `RoleRegistry`, live binding via `bind_skill_to_role` / `unbind_skill_from_role`.
    6. Footer Actions: Update, Open in Finder (`QDesktopServices`), Remove Skill.

### 2.4 EventBus & Inspector Telemetry (`atbmind_core/runtime/event_bus.py`, `bridge.py`)
- Events:
  - `SkillInstalledEvent(RuntimeEvent)`
  - `SkillUpdatedEvent(RuntimeEvent)`
  - `SkillBoundRoleEvent(RuntimeEvent)`
- Bridge signals:
  - `skill_installed`, `skill_updated`, `skill_bound_role`.
- Inspector integration:
  - Synchronizes available skills in `InspectorPanel`.

---

## 3. Implementation Task List

- [ ] Task 1: Background Workers (`SkillImportWorker`, `SkillUpdateWorker`) in `apps/atbmind_desktop/workers.py`
- [ ] Task 2: Import & Scaffolding Dialogs (`GitHubImportDialog`, `NewSkillDialog`, `LocalImportDialog`) in `apps/atbmind_desktop/widgets/skill_dialogs.py`
- [ ] Task 3: `SkillDetailDrawer` with Markdown preview, tools schema inspector, requirements checker, and role checkboxes in `apps/atbmind_desktop/widgets/skill_drawer.py`
- [ ] Task 4: Global EventBus events & Qt Bridge telemetry integration in `event_bus.py`, `bridge.py`, and `main_window.py`
- [ ] Task 5: Drawer & Dialogs integration into `SkillHubView` and `WorkStreamArea`
- [ ] Task 6: Comprehensive Unit & Integration test suite in `tests/test_skills_e2e_integration.py`
- [ ] Task 7: Verification & Full regression pass across all 320+ tests
- [ ] Task 8: `grill-me` stress-test audit & review transition
