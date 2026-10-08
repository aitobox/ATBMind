# Technical Specification: Desktop Native SkillHubView & Card Grid

## 1. Context & Objectives

- **Issue**: [#55 [skill-mgr] 构建桌面端原生 SkillHubView 工作台与卡片网格](https://github.com/aitobox/ATBMind/issues/55)
- **Parent Epic**: [#51 [Epic] ATBMind Skill Manager: 集成集中管理、更新、新建、本地与 GitHub 仓库技能导入系统](https://github.com/aitobox/ATBMind/issues/51)
- **Sequence**: Step 4 of 5 (Depends on #54, blocks #56)
- **Target Framework**: PySide6, Apple HIG design system (`apps/atbmind_desktop/theme.py`)

### Problem Statement
Users currently have no graphical desktop entry point to view, inspect, search, filter, enable/disable, or update skills. Skills were previously accessible only via Python APIs or the newly introduced `atbmind_skills.py` CLI. 

This issue implements Stage 4 of the Skill Manager: creating an Apple HIG native desktop workbench `SkillHubView`, embedding it seamlessly into the left navigation sidebar and central `WorkStreamArea`, and providing an interactive card grid `SkillCard` with search/filtering capabilities.

---

## 2. Architecture & Component Design

```
+----------------------------------------------------------------------------------------------------+
| ATBMind MainWindow (3-Pane Splitter)                                                              |
|                                                                                                    |
| +------------------------+ +---------------------------------------------------------------------+ |
| | NavigationSidebar      | | WorkStreamArea                                                      | |
| |                        | |                                                                     | |
| | [Top Bar / Controls]   | | [BreadcrumbHeaderBar: ATBMind / Skills Hub]                        | |
| | [+ New Conversation]   | |                                                                     | |
| | [History]              | | +-----------------------------------------------------------------+ | |
| | [Scheduled Tasks]      | | | QStackedWidget                                                  | | |
| | [🧩 Skills]  <---------+-+-+-> [Page 0: ChatStreamView]                                      | | |
| |                        | |   [Page 1: SkillHubView]                                          | | |
| | PINNED CONVERSATIONS   | |   +-------------------------------------------------------------+ | | |
| |  ...                   | |   | SkillHubView Header Toolbar:                                | | | |
| | PROJECTS               | |   |  [🔍 Pill Search Input]  [Pills: All|Enabled|Updates|...]   | | | |
| |  ...                   | |   |  [+ New]  [⬇️ Import]  [🔄 Check Updates]                   | | | |
| |                        | |   +-------------------------------------------------------------+ | | |
| |                        | |   | Responsive SkillCard Grid (Flow/Grid in QScrollArea)        | | | |
| |                        | |   |  +--------------------+  +--------------------+             | | | |
| |                        | |   |  | SkillCard          |  | SkillCard          |             | | | |
| |                        | |   |  | title + version    |  | title + version    |             | | | |
| |                        | |   |  | [source badge] [O] |  | [source badge] [O] |             | | | |
| |                        | |   |  | description ...    |  | description ...    |             | | | |
| |                        | |   |  | tags / roles pills |  | tags / roles pills |             | | | |
| |                        | |   |  | [Update Button]    |  | ...                |             | | | |
| |                        | |   |  +--------------------+  +--------------------+             | | | |
| |                        | |   +-------------------------------------------------------------+ | | |
| |                        | | +-----------------------------------------------------------------+ | |
| | [Settings]             | | [AgentPromptDock (hidden or disabled in hub mode if desired)]      | | |
| +------------------------+ +---------------------------------------------------------------------+ |
+----------------------------------------------------------------------------------------------------+
```

### 2.1 NavigationSidebar System Links
- In `apps/atbmind_desktop/widgets/navigation_sidebar.py`:
  - Add `self.btn_skills = QPushButton("Skills", self)` in `nav_links_layout`.
  - Icon: `get_apple_icon("puzzle")`.
  - Signal: `skills_requested = Signal()`.
  - Clicking `btn_skills` emits `skills_requested`.
  - Visual feedback: Highlight active state and support deselect when a session or new conversation is activated.

### 2.2 WorkStreamArea QStackedWidget Refactor
- In `apps/atbmind_desktop/widgets/work_stream.py`:
  - Wrap central area with `QStackedWidget`:
    - Page 0: `self.chat_stream = ChatStreamView(self)`
    - Page 1: `self.skill_hub = SkillHubView(self)`
  - Methods:
    - `show_chat_view()`: Sets stack index to 0. Restores breadcrumb session path. Shows prompt dock.
    - `show_skill_hub_view()`: Sets stack index to 1. Sets breadcrumb to `ATBMind / Skills Hub`. Optionally hides or retains prompt dock. Refreshes skill cards.
    - `current_view_name()` -> `"chat"` | `"skills"`.
  - MainWindow wiring:
    - `sidebar.skills_requested` -> `work_stream.show_skill_hub_view()`
    - `sidebar.session_selected` -> `work_stream.show_chat_view()`
    - `sidebar.new_session_requested` -> `work_stream.show_chat_view()`

### 2.3 SkillCard Component (`apps/atbmind_desktop/widgets/skill_hub.py`)
- Visual Design (Apple HIG light card):
  - Background: White (`#FFFFFF`), border `1px solid rgba(0, 0, 0, 0.08)`, border-radius `12px`.
  - Hover: Border color transitions to `rgba(0, 122, 255, 0.35)`, subtle shadow.
  - Header Row:
    - Title: Bold 14px (`ThemeColors.TEXT_PRIMARY`).
    - Version: Subtle muted pill (e.g. `v1.0.0`).
    - Source Badge:
      - GitHub: Blue tint badge `GitHub: {repo}`
      - Project: Purple tint badge `Project`
      - Global: Emerald/gray tint badge `Global`
      - Local: Slate tint badge `Local`
    - Enabled Switch: Apple-style toggle switch (`SwitchToggle` or `QCheckBox` styled as pill switch). Emits `skill_toggled(skill_name, enabled)`.
  - Description:
    - 2-line wrapped text with ellipsis (`ThemeColors.TEXT_SECONDARY`, 12px).
  - Tags Row:
    - Pill labels (e.g. `#productivity`, `#custom`).
  - Footer Row:
    - Bound Roles: Avatar/icon tags (e.g. `🤖 draw_expert`).
    - Update button: Displayed or highlighted when `source.has_update` is True (`Update` with amber/blue pill button). Emits `update_requested(skill_name)`.
  - Card Click:
    - Emits `clicked = Signal(str)` (skill name) for Stage 5 drawer opening.

### 2.4 SkillHubView Component (`apps/atbmind_desktop/widgets/skill_hub.py`)
- Header Toolbar:
  - Search Input: Pill rounded `QLineEdit` with magnifying glass icon `search`, placeholder: `搜索技能名称、描述或标签...`. Emits `textChanged`.
  - Filter Pills: Mutual exclusion / checkable pill buttons:
    - `All` (`全部`) [Default]
    - `Enabled` (`已启用`)
    - `Updates` (`有更新`)
    - `With Tools` (`含工具代码`)
    - `Project` (`项目内置`)
    - `Global` (`全局库`)
  - Action Buttons:
    - `+ New` (`+ 新建技能`) -> `new_skill_requested = Signal()`
    - `⬇️ Import` (`⬇️ 导入技能`) -> `import_requested = Signal()`
    - `🔄 Check Updates` (`🔄 检查更新`) -> `check_updates_requested = Signal()`
- Grid Container:
  - `QScrollArea` wrapping a dynamic grid of `SkillCard` items (minimum column width 300px, 2-3 columns depending on resize).
  - Dynamic filtering: Filtering by query + active pill instantly hides/shows or rebuilds cards without flicker.
  - Empty state widget when no skills match filters.
- Signals:
  - `skill_clicked = Signal(str)`
  - `skill_toggled = Signal(str, bool)`
  - `new_skill_requested = Signal()`
  - `import_requested = Signal()`
  - `check_updates_requested = Signal()`
  - `skill_update_requested = Signal(str)`

### 2.5 Vector Icons (`apps/atbmind_desktop/icons.py`)
- Add `puzzle`, `download`, `refresh` vector templates in `_SVG_TEMPLATES`.

---

## 3. Implementation Task List

- [x] Task 1: Vector icons extension (`puzzle`, `download`, `refresh` in `icons.py`)
- [x] Task 2: Navigation sidebar `🧩 Skills` item & signal emission in `navigation_sidebar.py`
- [x] Task 3: `SkillCard` and `SkillHubView` components in `apps/atbmind_desktop/widgets/skill_hub.py`
- [x] Task 4: `WorkStreamArea` `QStackedWidget` refactoring and view routing in `work_stream.py` and `main_window.py`
- [x] Task 5: Unit & GUI test suite in `tests/test_skills_ui.py`
- [x] Task 6: Verification & Full regression pass (`pytest tests/`)
- [x] Task 7: `grill-me` stress-test audit & review transition
