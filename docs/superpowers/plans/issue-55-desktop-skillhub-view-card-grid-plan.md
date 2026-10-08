# Implementation Plan: Desktop Native SkillHubView & Card Grid (Issue #55)

## Overview
Implement the Apple HIG desktop workbench `SkillHubView` and card grid `SkillCard` for Stage 4 of the Skill Manager Epic (#51). Integrate the view into `WorkStreamArea` via a `QStackedWidget`, wire navigation signals from `NavigationSidebar`, and verify thoroughly with `tests/test_skills_ui.py`.

---

## Detailed Task Breakdown

### Task 1: Vector Icons Extension
- **File**: `apps/atbmind_desktop/icons.py`
- **Changes**:
  - Add SVG templates to `_SVG_TEMPLATES`:
    - `puzzle`: 16x16 crisp puzzle piece for skills sidebar item.
    - `download`: 16x16 arrow down / tray icon for importing skills.
    - `refresh`: 16x16 circular arrows for checking updates.
- **Verification**: `python -c "from apps.atbmind_desktop.icons import get_apple_icon; print(get_apple_icon('puzzle'))"`

### Task 2: Navigation Sidebar `🧩 Skills` Item
- **File**: `apps/atbmind_desktop/widgets/navigation_sidebar.py`
- **Changes**:
  - Define `skills_requested = Signal()` on `NavigationSidebar`.
  - In `_init_ui()`, inside `nav_links_layout` (below `btn_history` and `btn_scheduled`), add:
    ```python
    self.btn_skills = QPushButton("Skills", self)
    self.btn_skills.setObjectName("navLinkBtn")
    self.btn_skills.setIcon(get_apple_icon("puzzle"))
    self.btn_skills.setCursor(Qt.CursorShape.PointingHandCursor)
    self.btn_skills.clicked.connect(self.skills_requested.emit)
    nav_links_layout.addWidget(self.btn_skills)
    ```
- **Verification**: Test sidebar button presence and signal emission in `test_skills_ui.py`.

### Task 3: `SkillCard` & `SkillHubView` Components
- **File**: `apps/atbmind_desktop/widgets/skill_hub.py`
- **Changes**:
  - Implement `SkillCard(QFrame)`:
    - Display title, version pill, source badge (`GitHub: repo`, `Project`, `Global`, `Local`).
    - Enabled switch/checkbox: emits `skill_toggled(skill_name, enabled)`.
    - 2-line description with ellipsis.
    - Tags pills.
    - Bound roles tags (e.g. `🤖 draw_expert`).
    - If `has_update` is True: Highlighted `Update` button emitting `update_requested(skill_name)`.
    - Mouse click on card emits `card_clicked(skill_name)`.
  - Implement `SkillHubView(QWidget)`:
    - Header toolbar:
      - Search `QLineEdit` with search icon and pill styling.
      - Filter pills: `All`, `Enabled`, `Updates`, `With Tools`, `Project`, `Global`.
      - Quick actions: `+ New`, `⬇️ Import`, `🔄 Check Updates`.
    - Grid of `SkillCard` items inside `QScrollArea`.
    - Responsive multi-column layout.
    - Methods: `load_skills()`, `set_skills(skills)`, `filter_skills()`.
    - Signals: `skill_clicked`, `skill_toggled`, `new_skill_requested`, `import_requested`, `check_updates_requested`, `skill_update_requested`.
- **Verification**: UI rendering and filter tests in `test_skills_ui.py`.

### Task 4: `WorkStreamArea` QStackedWidget Refactoring & View Routing
- **Files**:
  - `apps/atbmind_desktop/widgets/work_stream.py`
  - `apps/atbmind_desktop/main_window.py`
- **Changes**:
  - In `WorkStreamArea`:
    - Add `QStackedWidget`:
      - Index 0: `self.chat_stream`
      - Index 1: `self.skill_hub = SkillHubView(self)`
    - Add `show_chat_view()` and `show_skill_hub_view()`.
    - In `show_skill_hub_view()`: updates breadcrumb to `ATBMind  /  Skills Hub`, triggers `self.skill_hub.load_skills()`.
    - In `show_chat_view()`: restores breadcrumb with project/session.
  - In `main_window.py`:
    - Connect `self.sidebar.skills_requested` to `self.work_stream.show_skill_hub_view`.
    - Connect `self.sidebar.session_selected` and `new_session_requested` to ensure `work_stream.show_chat_view()` is called.
- **Verification**: Switch tests in `test_skills_ui.py`.

### Task 5: Unit & GUI Test Suite
- **File**: `tests/test_skills_ui.py`
- **Test Cases**:
  - `test_sidebar_skills_button_and_signal`
  - `test_skill_card_rendering_and_badges`
  - `test_skill_card_signals`
  - `test_skill_hub_search_filtering`
  - `test_skill_hub_pill_category_filtering`
  - `test_work_stream_stacked_widget_routing`
  - `test_main_window_skills_navigation_integration`
- **Verification**: `PYTHONPATH=. conda run -n ATBMind pytest tests/test_skills_ui.py`

### Task 6: Full Regression Pass
- Run complete test suite:
  `PYTHONPATH=. conda run -n ATBMind python -m pytest tests/`
- Ensure all 312+ tests pass with 0 regressions.

### Task 7: Audit & Review Transition
- Run `grill-me` audit against the checklist.
- Transition state to `reviewing`.
