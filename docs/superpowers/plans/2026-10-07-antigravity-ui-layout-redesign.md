# Antigravity 3-Pane UI Layout Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign ATBMind Desktop layout into an Antigravity-inspired 3-pane workbench (Left Navigation Sidebar, Center Stream & Agent Prompt Dock, Right Inspector Panel) with live `AsyncEventBus` integration, queued message scheduling, and project-aware session hierarchy.

**Architecture:** A modern `QSplitter`-based layout containing `NavigationSidebar`, `WorkStreamArea`, and `InspectorPanel`. An asynchronous `EventBusQtBridge` consumes runtime events from `AsyncEventBus` and safely dispatches Qt signals to update subagent indicators, background tasks, and inspector accordion sections on the main GUI thread.

**Tech Stack:** Python 3.12, PySide6, pytest, pytest-qt, Pydantic v2, asyncio

**Spec:** `docs/superpowers/specs/2026-10-07-antigravity-ui-layout-redesign-design.md`

## Global Constraints

- Pane minimum dimensions: Left Sidebar min `200px` (default `260px`), Center min `460px` (stretch `1`), Right Inspector min `240px` (default `300px`).
- Splitter handles styled to 1px subtle divider lines (`ThemeColors.BORDER_SUBTLE`, `#E5E5EA`); `setChildrenCollapsible(False)`.
- Thread safety: Never mutate PySide6 widgets directly from asyncio event loop threads; route all runtime telemetry through `EventBusQtBridge` Qt signals.
- Backward compatibility: `SessionRecord` additions (`workspace_name`, `is_pinned`) must supply default values to prevent breaking existing SQLite databases.
- Shortcuts: `Cmd+B` / `Ctrl+B` for sidebar toggle; `Cmd+Shift+I` / `Ctrl+Shift+I` for inspector toggle.

## Review Focus

1. Splitter resize or window shrink below minimum limits must not cause zero-width collapse or GUI clipping.
2. Multiple rapid prompts submitted while `in_flight=True` must correctly append to FIFO queue without dropped messages or out-of-order execution.
3. Rapid `SubagentLifecycleEvent` state transitions (running -> idle -> done) must update UI indicators smoothly without UI freeze or stale spinners.
4. Pinning/unpinning sessions must update both Pinned and Project tree sections reactively without deselecting the current active session.
5. If `AsyncEventBus` is absent or uninitialized, UI components and `main_window` must degrade gracefully without raising `AttributeError` or crashing.

---

### Task 1: Session Schema & State Manager Enhancements

**Files:**
- Modify: `atbmind_core/storage/schemas.py:14-37`
- Modify: `apps/atbmind_desktop/state.py:14-86`
- Test: `tests/test_session_schema_and_state.py`

**Interfaces:**
- Consumes: `SessionRecord`, `UIStateManager`
- Produces:
  - `SessionRecord.workspace_name: str = "ATBMind"`
  - `SessionRecord.is_pinned: bool = False`
  - `UIStateManager.toggle_session_pinned(session_id: str) -> bool`
  - `UIStateManager.queue_prompt(session_id: str, prompt: str) -> int`
  - `UIStateManager.pop_queued_prompt(session_id: str) -> Optional[str]`
  - `UIStateManager.get_queued_prompts(session_id: str) -> list[str]`
  - `UIStateManager.remove_queued_prompt(session_id: str, index: int) -> bool`
  - `UIStateManager.queued_prompts_changed = Signal(str, list)`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_session_schema_and_state.py
from atbmind_core.storage.schemas import SessionRecord
from apps.atbmind_desktop.state import UIStateManager


def test_session_record_workspace_and_pinned():
    session = SessionRecord(session_id="s1", title="Test")
    assert session.workspace_name == "ATBMind"
    assert session.is_pinned is False

    session_pinned = SessionRecord(
        session_id="s2", title="Pinned", workspace_name="RepoA", is_pinned=True
    )
    assert session_pinned.workspace_name == "RepoA"
    assert session_pinned.is_pinned is True


def test_ui_state_manager_queued_prompts(qtbot):
    state = UIStateManager()
    session = SessionRecord(session_id="s1", title="Test")
    state.cache_session(session)

    # Pin toggle
    is_pinned = state.toggle_session_pinned("s1")
    assert is_pinned is True
    assert state.get_cached_session("s1").is_pinned is True

    # Prompt queuing
    with qtbot.waitSignal(state.queued_prompts_changed, timeout=1000) as blocker:
        state.queue_prompt("s1", "prompt 1")
    assert blocker.args == ["s1", ["prompt 1"]]
    assert state.get_queued_prompts("s1") == ["prompt 1"]

    state.queue_prompt("s1", "prompt 2")
    assert state.get_queued_prompts("s1") == ["prompt 1", "prompt 2"]

    popped = state.pop_queued_prompt("s1")
    assert popped == "prompt 1"
    assert state.get_queued_prompts("s1") == ["prompt 2"]

    state.remove_queued_prompt("s1", 0)
    assert state.get_queued_prompts("s1") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_session_schema_and_state.py -v`
Expected: FAIL with attribute errors on `workspace_name` or `toggle_session_pinned`.

- [ ] **Step 3: Implement enhancements in schemas.py and state.py**

1. In `atbmind_core/storage/schemas.py`, add `workspace_name: str = Field(default="ATBMind")` and `is_pinned: bool = Field(default=False)` to `SessionRecord`.
2. In `apps/atbmind_desktop/state.py`, add `queued_prompts_changed = Signal(str, list)` and dictionary `self._queued_prompts: dict[str, list[str]] = {}`.
3. Implement `toggle_session_pinned`, `queue_prompt`, `pop_queued_prompt`, `get_queued_prompts`, and `remove_queued_prompt`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_session_schema_and_state.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add atbmind_core/storage/schemas.py apps/atbmind_desktop/state.py tests/test_session_schema_and_state.py
git commit -m "feat(state): extend SessionRecord with workspace/pinned fields and queue manager"
```

---

### Task 2: Thread-Safe `EventBusQtBridge`

**Files:**
- Create: `apps/atbmind_desktop/bridge.py`
- Test: `tests/test_event_bus_qt_bridge.py`

**Interfaces:**
- Consumes: `atbmind_core.runtime.event_bus.AsyncEventBus`, `SubagentLifecycleEvent`, `TaskStatusChangedEvent`, `TimerFiredEvent`
- Produces:
  - `class EventBusQtBridge(QObject)`:
    - `subagent_lifecycle_changed = Signal(str, str, str)` # id, state, detail
    - `task_status_changed = Signal(str, str, str)` # id, status, summary
    - `timer_fired = Signal(str, str, bool)` # id, prompt, is_cron
    - `skill_activated = Signal(str, str)` # skill_name, skill_path
    - `files_changed_updated = Signal(list)` # diff_list
    - `attach_bus(bus: AsyncEventBus)`
    - `detach_bus()`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_event_bus_qt_bridge.py
import pytest
from PySide6.QtCore import QCoreApplication
from atbmind_core.runtime.event_bus import (
    AsyncEventBus,
    SubagentLifecycleEvent,
    TaskStatusChangedEvent,
    TimerFiredEvent,
)
from apps.atbmind_desktop.bridge import EventBusQtBridge


@pytest.mark.asyncio
async def test_event_bus_qt_bridge_signals(qtbot):
    bus = AsyncEventBus()
    bridge = EventBusQtBridge()
    bridge.attach_bus(bus)

    # SubagentLifecycleEvent
    with qtbot.waitSignal(bridge.subagent_lifecycle_changed, timeout=1000) as subagent_signal:
        await bus.publish(
            SubagentLifecycleEvent(subagent_id="sub-1", state="running", detail="Working on step 1")
        )
    assert subagent_signal.args == ["sub-1", "running", "Working on step 1"]

    # TaskStatusChangedEvent
    with qtbot.waitSignal(bridge.task_status_changed, timeout=1000) as task_signal:
        await bus.publish(
            TaskStatusChangedEvent(source_id="task-1", old_status="pending", new_status="done", summary="Build complete")
        )
    assert task_signal.args == ["task-1", "done", "Build complete"]

    bridge.detach_bus()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_event_bus_qt_bridge.py -v`
Expected: FAIL with "No module named apps.atbmind_desktop.bridge".

- [ ] **Step 3: Implement `EventBusQtBridge` in `apps/atbmind_desktop/bridge.py`**

1. Define `EventBusQtBridge(QObject)` with signals for subagents, background tasks, timers, skills, and files changed.
2. In `attach_bus(bus)`, subscribe sync/async handler callbacks that emit the corresponding Qt signals using `Signal.emit()`.
3. In `detach_bus()`, unsubscribe handlers.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_event_bus_qt_bridge.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/atbmind_desktop/bridge.py tests/test_event_bus_qt_bridge.py
git commit -m "feat(desktop): add EventBusQtBridge for thread-safe runtime event telemetry"
```

---

### Task 3: Antigravity Modern Navigation Sidebar

**Files:**
- Create: `apps/atbmind_desktop/widgets/navigation_sidebar.py`
- Test: `tests/test_navigation_sidebar_antigravity.py`

**Interfaces:**
- Consumes: `SessionRecord`, `ThemeColors`, `ThemeFonts`
- Produces:
  - `class NavigationSidebar(QWidget)`:
    - Signals:
      - `new_session_requested = Signal()`
      - `session_selected = Signal(str)`
      - `session_pin_toggled = Signal(str)`
      - `session_rename_requested = Signal(str, str)`
      - `session_delete_requested = Signal(str)`
      - `open_settings_requested = Signal()`
      - `sidebar_collapse_requested = Signal()`
    - Methods:
      - `set_sessions(sessions: list[SessionRecord], active_session_id: Optional[str] = None)`
      - `set_in_flight(session_id: str, is_in_flight: bool)`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_navigation_sidebar_antigravity.py
import pytest
from atbmind_core.storage.schemas import SessionRecord
from apps.atbmind_desktop.widgets.navigation_sidebar import NavigationSidebar


def test_navigation_sidebar_rendering_and_signals(qtbot):
    sidebar = NavigationSidebar()
    qtbot.addWidget(sidebar)

    sessions = [
        SessionRecord(session_id="s1", title="Pinned Task", workspace_name="ATBMind", is_pinned=True),
        SessionRecord(session_id="s2", title="Project Task", workspace_name="ATBMind", is_pinned=False),
    ]
    sidebar.set_sessions(sessions, active_session_id="s2")

    # Verify Pinned list count is 1 and Projects list has 1 item under ATBMind
    assert sidebar.pinned_count() == 1
    assert sidebar.project_session_count("ATBMind") == 1

    # Verify new session trigger
    with qtbot.waitSignal(sidebar.new_session_requested, timeout=1000):
        sidebar.btn_new.click()

    # Verify collapse trigger
    with qtbot.waitSignal(sidebar.sidebar_collapse_requested, timeout=1000):
        sidebar.btn_toggle.click()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_navigation_sidebar_antigravity.py -v`
Expected: FAIL with "No module named apps.atbmind_desktop.widgets.navigation_sidebar".

- [ ] **Step 3: Implement `NavigationSidebar` in `apps/atbmind_desktop/widgets/navigation_sidebar.py`**

1. Build top controls: Traffic light margin, `btn_toggle` (`[|]`), history back/forward buttons.
2. Build `btn_new`: `+ New Conversation` card button.
3. Build utility links: `Conversation History` and `Scheduled Tasks`.
4. Build `PinnedListWidget`: Displays `is_pinned=True` sessions in 2-line cards (title + timestamp, workspace icon + name).
5. Build `ProjectsTreeWidget`: Group sessions by `workspace_name`, render project folder nodes, display conversation rows with timestamps and hover `[...]` button.
6. Connect right-click / `[...]` context menu with Pin/Unpin, Rename, Delete.
7. Bottom pinned `Settings` button.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_navigation_sidebar_antigravity.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/atbmind_desktop/widgets/navigation_sidebar.py tests/test_navigation_sidebar_antigravity.py
git commit -m "feat(ui): add NavigationSidebar with projects tree, pinned cards, and Antigravity styling"
```

---

### Task 4: Composite Agent Prompt Dock

**Files:**
- Create: `apps/atbmind_desktop/widgets/agent_dock.py`
- Test: `tests/test_agent_prompt_dock.py`

**Interfaces:**
- Consumes: `ThemeColors`, `ThemeFonts`, `ThemeRadii`
- Produces:
  - `class QueuedMessagesWidget(QWidget)`:
    - Signals: `send_now_requested(int)`, `edit_requested(int)`, `delete_requested(int)`
    - Methods: `set_queued_messages(prompts: list[str])`
  - `class SubagentRunningBanner(QWidget)`:
    - Methods: `set_running_subagents(subagents: list[tuple[str, str]])` # id, name
  - `class AgentInputCard(QWidget)`:
    - Signals: `submit_requested(str, dict)`
    - Methods: `set_prompt_text(text: str)`, `get_prompt_text() -> str`, `clear()`
  - `class AgentPromptDock(QWidget)`:
    - Signals: `submit_requested(str, dict)`, `queue_action(str, int)`
    - Combines all three layers into a single responsive dock.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_agent_prompt_dock.py
import pytest
from apps.atbmind_desktop.widgets.agent_dock import (
    AgentPromptDock,
    QueuedMessagesWidget,
    SubagentRunningBanner,
)


def test_queued_messages_widget(qtbot):
    w = QueuedMessagesWidget()
    qtbot.addWidget(w)
    assert not w.isVisible()

    w.set_queued_messages(["/grill-me please check code"])
    assert w.isVisible()
    assert w.count() == 1

    with qtbot.waitSignal(w.delete_requested, timeout=1000) as sig:
        w.trigger_delete(0)
    assert sig.args == [0]


def test_subagent_running_banner(qtbot):
    b = SubagentRunningBanner()
    qtbot.addWidget(b)
    assert not b.isVisible()

    b.set_running_subagents([("sub1", "Task 1 Reviewer")])
    assert b.isVisible()
    assert "Task 1 Reviewer" in b.text()


def test_agent_prompt_dock_submission(qtbot):
    dock = AgentPromptDock()
    qtbot.addWidget(dock)

    dock.input_card.set_prompt_text("Hello Agent")
    with qtbot.waitSignal(dock.submit_requested, timeout=1000) as sig:
        dock.input_card.btn_send.click()
    prompt, payload = sig.args
    assert prompt == "Hello Agent"
    assert "model" in payload
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_agent_prompt_dock.py -v`
Expected: FAIL with "No module named apps.atbmind_desktop.widgets.agent_dock".

- [ ] **Step 3: Implement `AgentPromptDock` in `apps/atbmind_desktop/widgets/agent_dock.py`**

1. Implement `QueuedMessagesWidget` with header `Queued Messages N Sends after agent finishes working` and item rows with `[➔]`, `[✎]`, `[🗑]` actions.
2. Implement `SubagentRunningBanner` with spinner animation and subagent list.
3. Implement `AgentInputCard` with rounded container (`16px`), auto-resizing text edit, `+` attach, model combobox dropdown, voice icon, and send circle button.
4. Stack them vertically inside `AgentPromptDock`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_agent_prompt_dock.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/atbmind_desktop/widgets/agent_dock.py tests/test_agent_prompt_dock.py
git commit -m "feat(ui): add AgentPromptDock with queued messages, running banner, and modern input card"
```

---

### Task 5: Work Stream Area & Timeline Items

**Files:**
- Create: `apps/atbmind_desktop/widgets/work_stream.py`
- Test: `tests/test_work_stream_area.py`

**Interfaces:**
- Consumes: `ChatStreamView`, `AgentPromptDock`
- Produces:
  - `class BreadcrumbHeaderBar(QWidget)`:
    - Signals: `open_ide_requested()`, `menu_requested()`
    - Methods: `set_breadcrumb(project: str, session_title: str)`
  - `class StepElapsedPill(QWidget)`: Collapsible step pill displaying `Worked for Xm >`
  - `class CodeChangeBadgeItem(QWidget)`: Displays `1 file changed +23 -0 >` with `[Review]` button
  - `class WorkStreamArea(QWidget)`: Integrates `BreadcrumbHeaderBar`, `ChatStreamView`, and `AgentPromptDock`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_work_stream_area.py
import pytest
from apps.atbmind_desktop.widgets.work_stream import (
    BreadcrumbHeaderBar,
    CodeChangeBadgeItem,
    StepElapsedPill,
    WorkStreamArea,
)


def test_breadcrumb_header_bar(qtbot):
    header = BreadcrumbHeaderBar()
    qtbot.addWidget(header)
    header.set_breadcrumb("ATBMind", "Codex Project Implementation Planning")
    assert "ATBMind" in header.label_path.text()
    assert "Codex Project" in header.label_path.text()

    with qtbot.waitSignal(header.open_ide_requested, timeout=1000):
        header.btn_open_ide.click()


def test_step_elapsed_pill(qtbot):
    pill = StepElapsedPill(text="Worked for 1m", details="Execution log line 1")
    qtbot.addWidget(pill)
    assert "Worked for 1m" in pill.title_label.text()
    assert not pill.details_widget.isVisible()
    pill.toggle_expand()
    assert pill.details_widget.isVisible()


def test_code_change_badge(qtbot):
    badge = CodeChangeBadgeItem(summary="1 file changed +23 -0")
    qtbot.addWidget(badge)
    assert "+23 -0" in badge.label.text()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_work_stream_area.py -v`
Expected: FAIL with "No module named apps.atbmind_desktop.widgets.work_stream".

- [ ] **Step 3: Implement `work_stream.py`**

1. Create `BreadcrumbHeaderBar` with styled `[Project] / [Session]` breadcrumb, `Open IDE` button, and `...` options.
2. Create `StepElapsedPill` with chevron toggle and collapsible log body.
3. Create `CodeChangeBadgeItem` with diff badge and `[Review]` action button.
4. Create `WorkStreamArea` combining `BreadcrumbHeaderBar`, `ChatStreamView`, and `AgentPromptDock`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_work_stream_area.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/atbmind_desktop/widgets/work_stream.py tests/test_work_stream_area.py
git commit -m "feat(ui): add WorkStreamArea with breadcrumbs, elapsed pills, and code diff badges"
```

---

### Task 6: Right Inspector Panel & Accordion Framework

**Files:**
- Create: `apps/atbmind_desktop/widgets/inspector_panel.py`
- Test: `tests/test_inspector_panel.py`

**Interfaces:**
- Consumes: `ThemeColors`, `ThemeFonts`, `ThemeRadii`
- Produces:
  - `class AccordionSection(QWidget)`:
    - Methods: `set_title(title: str, count: Optional[int] = None)`, `set_expanded(expanded: bool)`, `add_item(widget: QWidget)`
  - `class InspectorHeaderBar(QWidget)`:
    - Signals: `tab_changed(int)`, `add_requested()`, `fullscreen_requested()`, `collapse_requested()`
  - `class InspectorPanel(QWidget)`:
    - Methods:
      - `update_subagent(id: str, name: str, state: str, elapsed: str)`
      - `update_files_changed(files: list[dict])`
      - `update_skills_used(skills: list[tuple[str, str]])`
      - `update_background_tasks(tasks: list[dict])`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_inspector_panel.py
import pytest
from apps.atbmind_desktop.widgets.inspector_panel import (
    AccordionSection,
    InspectorPanel,
)


def test_accordion_section(qtbot):
    section = AccordionSection(title="Subagents", count=2)
    qtbot.addWidget(section)
    assert section.is_expanded()
    assert "Subagents" in section.header_title.text()
    assert "2" in section.count_badge.text()

    section.toggle_expanded()
    assert not section.is_expanded()


def test_inspector_panel_updates(qtbot):
    panel = InspectorPanel()
    qtbot.addWidget(panel)

    panel.update_subagent("sub1", "Task 1 Reviewer", "running", "Working...")
    panel.update_subagent("sub2", "Task 1 Implementer", "done", "Worked for 6m")
    assert panel.subagent_count() == 2

    panel.update_skills_used([
        ("subagent-driven-development", "skills/sdd"),
        ("writing-plans", "skills/writing-plans"),
    ])
    assert panel.skills_count() == 2

    with qtbot.waitSignal(panel.header.collapse_requested, timeout=1000):
        panel.header.btn_collapse.click()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_inspector_panel.py -v`
Expected: FAIL with "No module named apps.atbmind_desktop.widgets.inspector_panel".

- [ ] **Step 3: Implement `InspectorPanel` in `apps/atbmind_desktop/widgets/inspector_panel.py`**

1. Implement `AccordionSection` with clean Antigravity header bar (chevron, title, count badge, optional header action) and collapsible content container.
2. Implement `InspectorHeaderBar` with view tabs, `+`, `⛶`, `[|]` buttons.
3. Build specialized sections:
   - `Subagents` (status indicators: spinner for running, checkmark for done, error icon for failed).
   - `Files Changed` (diff badge and filter dropdown).
   - `Artifacts`, `Uploads`, `Background Tasks`, `Terminals`.
   - `Skills Used` (document icon, skill name, abbreviated path).
4. Assemble inside scrollable `InspectorPanel`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_inspector_panel.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/atbmind_desktop/widgets/inspector_panel.py tests/test_inspector_panel.py
git commit -m "feat(ui): add InspectorPanel with accordions for subagents, files changed, and skills"
```

---

### Task 7: 3-Pane `QSplitter` Assembly in `ATBMindMainWindow` & Full Integration

**Files:**
- Modify: `apps/atbmind_desktop/main_window.py:50-160`
- Test: `tests/test_atbmind_3_pane_main_window.py`

**Interfaces:**
- Consumes: `NavigationSidebar`, `WorkStreamArea`, `InspectorPanel`, `EventBusQtBridge`, `UIStateManager`
- Produces:
  - `ATBMindMainWindow` with responsive 3-pane `QSplitter`.
  - Sidebar toggle (`Cmd+B`), Inspector toggle (`Cmd+Shift+I`).
  - Signal wiring between `EventBusQtBridge`, `UIStateManager`, `WorkStreamArea`, and `InspectorPanel`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_atbmind_3_pane_main_window.py
import pytest
from PySide6.QtCore import Qt
from apps.atbmind_desktop.main_window import ATBMindMainWindow


def test_main_window_3_pane_splitter(qtbot):
    win = ATBMindMainWindow()
    qtbot.addWidget(win)

    # Verify 3 panes exist in splitter
    assert win.splitter.count() == 3
    assert win.sidebar.isVisible()
    assert win.work_stream.isVisible()
    assert win.inspector.isVisible()

    # Toggle sidebar
    win.toggle_sidebar()
    assert not win.sidebar.isVisible()
    win.toggle_sidebar()
    assert win.sidebar.isVisible()

    # Toggle inspector
    win.toggle_inspector()
    assert not win.inspector.isVisible()
    win.toggle_inspector()
    assert win.inspector.isVisible()

    # Breadcrumb syncs with session
    assert win.work_stream.header.get_project_name() == "ATBMind"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_atbmind_3_pane_main_window.py -v`
Expected: FAIL with attribute errors on `splitter` or `inspector`.

- [ ] **Step 3: Refactor `main_window.py` to assemble the 3 panes**

1. Replace fixed `QHBoxLayout` with `QSplitter(Qt.Orientation.Horizontal)`.
2. Add `sidebar` (`NavigationSidebar`), `work_stream` (`WorkStreamArea`), `inspector` (`InspectorPanel`).
3. Set splitter sizes `[260, 640, 300]` and `setChildrenCollapsible(False)`.
4. Add `toggle_sidebar()` and `toggle_inspector()` methods, bind to `QShortcut` for `Cmd+B` and `Cmd+Shift+I`.
5. Connect `EventBusQtBridge` signals to `inspector` and `work_stream`.
6. Connect `UIStateManager` queued prompt dispatcher when workers complete.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_atbmind_3_pane_main_window.py -v`
Expected: PASS

- [ ] **Step 5: Run all desktop tests to ensure zero regressions**

Run: `pytest tests/ -k desktop -v`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/atbmind_desktop/main_window.py tests/test_atbmind_3_pane_main_window.py
git commit -m "feat(desktop): assemble 3-pane Antigravity layout with QSplitter and full signal wiring"
```
