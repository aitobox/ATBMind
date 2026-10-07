# ATBMind Desktop UI Antigravity 3-Pane Layout Redesign Specification

## 1. Overview & Architectural Goals

### 1.1 Background & Context
ATBMind is advancing from an early dual-column desktop tool into a fully-fledged autonomous agent workbench and harness. The current user interface features a two-column structure (Sidebar + Chat Container with legacy image plugin controls). To support modern multi-agent programming, subagent orchestration, tool telemetry, and code review workflows, ATBMind requires a modern, responsive three-pane layout inspired by Google Antigravity.

### 1.2 Core Goals
1. **Three-Pane Responsive Splitter**: Replace the rigid two-column layout with a seamless horizontal `QSplitter` containing:
   - **Left Pane (Navigation Sidebar)**: Project tree, pinned conversations, history, scheduled tasks, and settings.
   - **Center Pane (Work Stream Area)**: Breadcrumb header, agent execution stream with collapsible step pills and code change cards, and a stacked input dock supporting queued messages and running subagent banners.
   - **Right Pane (Inspector Panel)**: Collapsible accordion monitor for subagents, files changed, artifacts, uploads, background tasks, terminals, and skills used.
2. **Event-Driven Telemetry via AsyncEventBus**: Bridge `atbmind_core.runtime.AsyncEventBus` to PySide6 via a thread-safe `EventBusQtBridge`, dynamically driving the subagent banner, task indicators, and inspector accordions.
3. **Queued Messages Pipeline**: Allow users to queue follow-up prompts while the agent is executing (`in_flight=True`), displaying pending prompts in a collapsible card with edit/delete/dispatch options.
4. **Data Model Compatibility**: Extend `SessionRecord` with `workspace_name` and `is_pinned` while preserving SQLite backward compatibility.

### 1.3 Non-Goals
- Native OS docking window detaching (floating windows): keep panels within the integrated splitter framework for design consistency.
- Overhauling backend agent execution algorithms in this phase (focus on UI layout, state bridging, and presentation layer).

---

## 2. Layout Architecture & Splitter System

```
+------------------------------------------------------------------------------------------------------------------------+
|                                                   ATBMind Desktop Window                                              |
|                                                     (QSplitter: Horizontal)                                            |
+------------------------------------+---------------------------------------------------+-------------------------------+
|  Left: NavigationSidebar (260px)   |  Center: WorkStreamArea (Flexible / Stretch 1)   |  Right: InspectorPanel (300px) |
|  - Window Controls / Nav arrows    |  - BreadcrumbHeaderBar                            |  - InspectorHeaderBar         |
|  - + New Conversation              |    (Project / Session, Open IDE)                  |    (View tabs, Add, Fullscreen|
|  - History & Scheduled Tasks       |  - AgentStreamTimeline                            |     Collapse right)           |
|  - Pinned Conversations            |    (User bubbles, Step elapsed pills,             |  - AccordionScrollArea        |
|  - Projects Tree (Workspace root)  |     Subagent notices, Code diff badges)           |    - Subagents (N)            |
|  - Settings (bottom pinned)        |  - AgentPromptDock                                |    - Files Changed (N)        |
|                                    |    - QueuedMessagesWidget                         |    - Artifacts (N)            |
|                                    |    - SubagentRunningBanner                        |    - Uploads (N)              |
|                                    |    - AgentInputCard (Model, Voice, Send)          |    - Background Tasks (N)     |
|                                    |                                                   |    - Terminals (N)            |
|                                    |                                                   |    - Skills Used (N)          |
+------------------------------------+---------------------------------------------------+-------------------------------+
```

### 2.1 Splitter Dimensions & Behavior
- **Left Pane (`NavigationSidebar`)**: Default width `260px`, min `200px`, max `360px`.
- **Center Pane (`WorkStreamArea`)**: Default width flexible (`stretch=1`), min `460px`.
- **Right Pane (`InspectorPanel`)**: Default width `300px`, min `240px`, max `480px`.
- **Dividers (`QSplitter::handle`)**: 1px subtle divider lines with color `ThemeColors.BORDER_SUBTLE` (`#E5E5EA`).
- **Collapsing**: `setChildrenCollapsible(False)`. Panels are toggled using explicit buttons and keyboard shortcuts.
  - Left Sidebar Toggle: `Cmd+B` / `Ctrl+B` (and top-left `[|]` button).
  - Right Inspector Toggle: `Cmd+Shift+I` / `Ctrl+Shift+I` (and top-right `[|]` button).
  - When toggling, previous panel width is cached and restored upon expansion.

---

## 3. Left Navigation Sidebar (`NavigationSidebar`)

### 3.1 Visual Components
1. **Header Area**:
   - macOS traffic lights padding.
   - Sidebar collapse icon button `[|]`.
   - History navigation back/forward buttons `<` and `>`.
2. **Primary Action**:
   - `+ New Conversation` card button: white/subtle card styling, 1px border, centered layout, shortcut `Cmd+N`.
3. **System Navigation Links**:
   - `Conversation History` with clock/history icon.
   - `Scheduled Tasks` with timer icon.
4. **Pinned Conversations (`PinnedListWidget`)**:
   - Header: `PINNED CONVERSATIONS` (11px uppercase bold, muted secondary text).
   - Items: Two-line presentation:
     - Line 1: Title (left) + relative timestamp like `4h`, `14d` (right).
     - Line 2: Folder icon + workspace name (e.g., `📁 ATBCmder`).
5. **Projects Tree (`ProjectsTreeWidget`)**:
   - Header: `PROJECTS` with right-aligned action buttons: filter icon and new project icon.
   - Project Node: `📁 ATBMind` (expandable/collapsible folder node).
   - Session Item:
     - Title + relative timestamp (e.g. `30m`, `2h`, `8d`).
     - Selected state: Light grey rounded capsule (`ThemeColors.BG_SIDEBAR_SELECTED`, radius `8px`).
     - Hover state: reveals `[...]` context action button.
6. **Footer Pin**:
   - `⚙ Settings` button permanently anchored at the bottom.

### 3.2 Context Actions (`[...]` and Right-Click)
- 📌 `Pin / Unpin Conversation`: Toggles `session.is_pinned`, moving item between Pinned and Project sections.
- ✏️ `Rename Conversation`: Opens inline title editor or input dialog.
- 🗑️ `Delete Conversation`: Confirms and purges session from store.

---

## 4. Center Work Area (`WorkStreamArea`)

### 4.1 Breadcrumb Header Bar (`BreadcrumbHeaderBar`)
- Left: Breadcrumb path `[Project Name] / [Session Title]` (e.g. `ATBMind / Codex Project Implementation Planning`).
- Right:
  - `[...]` Session settings and clear history menu.
  - `Open IDE` button: styled with modern code icon, launches active project in system editor or configured IDE.

### 4.2 Stream Timeline (`AgentStreamTimeline`)
Enhanced message stream rendering distinct lifecycle items:
1. **User Query Bubble**: Clean typography, left/right aligned, subtle background.
2. **Step Elapsed Pill (`StepElapsedPill`)**:
   - Displays `Worked for 1m >` or `Worked for 33s >`.
   - Collapsible: clicking toggles internal thinking/log details.
3. **Subagent Notice Item (`SubagentNoticeItem`)**:
   - Informational status text: `Waiting for Task 1 implementer subagent to complete work and report.`
   - Subagent message badge: `Message from Task 1 Implementer (self) >`.
4. **Code Change Badge Card (`CodeChangeBadgeItem`)**:
   - Displays `1 file changed +23 -0 >`.
   - Right button: `[Review]` pill button that triggers diff viewer dialog or tab.
5. **Message Actions Bar**:
   - Copy to clipboard, thumbs up, and thumbs down icons.

### 4.3 Composite Bottom Dock (`AgentPromptDock`)
A vertical composite stack composed of three layers:
1. **Layer 1: Queued Messages Box (`QueuedMessagesWidget`)**:
   - Only visible when one or more messages are queued.
   - Header: `⮟ Queued Messages [Count] - Sends after agent finishes working`.
   - Item row: shows pending prompt text (e.g. `/grill-me ...`) with actions:
     - `[➔]` Send now (force dispatch).
     - `[✎]` Edit pending text.
     - `[🗑]` Remove from queue.
2. **Layer 2: Subagents Running Banner (`SubagentRunningBanner`)**:
   - Active when subagents are running.
   - Header: `⮟ N subagent(s) running`.
   - Item: animated spinner + subagent name (e.g., `⏳ Task 1 Reviewer`).
3. **Layer 3: Agent Input Card (`AgentInputCard`)**:
   - Modern container with `16px` border-radius and subtle focus border.
   - Auto-resizing text area with placeholder `Ask anything, @ to mention, / for actions`.
   - Integrated tool row:
     - Left: `[+]` file/image attachment button; Model selection combobox dropdown (e.g. `Gemini 3.8 Flash High ▾`).
     - Right: `[🎙]` voice dictation button; `[➔]` primary circular send button.

---

## 5. Right Inspector Panel (`InspectorPanel`)

### 5.1 Inspector Header Bar (`InspectorHeaderBar`)
- Left: View mode tabs (`[📝 Context]`, `[📂 Files]`, `[🖼️ Artifacts]`).
- Right: Action buttons:
  - `[+]` New task / subagent spawn.
  - `[⛶]` Fullscreen / undock preview.
  - `[|]` Collapse right panel.

### 5.2 Accordion Sections (`AccordionSection`)
Unified collapsible accordion component with header title, count badge, optional header widget, chevron arrow (`⮟` / `⮞`), and child content widget.

1. **Subagents Section**:
   - Header: `Subagents [Count]` with right `[🎯 Target]` trigger.
   - List of subagents:
     - Name (e.g. `Task 1 Reviewer`, `Task 1 Implementer`).
     - Subtitle status (e.g. `Working...`, `Worked for 6m`).
     - Status indicator: rotating spinner for active, checkmark circle `✓` for completed, warning icon for failed.
2. **Files Changed Section**:
   - Header: `Files Changed [Count]` with right dropdown filter (`Uncommitted ▾`, `Staged`, `All`).
   - Changed file list with path and diff stats (`+23 -0`).
3. **Artifacts Section**:
   - Header: `Artifacts [Count]`.
   - Lists generated markdown specs, diagrams, and export files.
4. **Uploads Section**:
   - Header: `Uploads [Count]`. Lists user-attached reference assets.
5. **Background Tasks Section**:
   - Header: `Background Tasks [Count]`. Lists active daemons or timers.
6. **Terminals Section**:
   - Header: `Terminals [Count]`. Lists interactive terminal instances.
7. **Skills Used Section**:
   - Header: `Skills Used [Count]`.
   - Lists active skills (e.g., `subagent-driven-development`, `writing-plans`, `antigravity-guide`, `brainstorming`) with document icons and truncated relative paths with tooltips.

---

## 6. State Management & Event-Driven Architecture

### 6.1 `EventBusQtBridge` Architecture
```python
class EventBusQtBridge(QObject):
    subagent_lifecycle_changed = Signal(str, str, str)  # id, state, detail
    task_status_changed = Signal(str, str, str)         # id, status, summary
    skill_activated = Signal(str, str)                  # name, path
    files_changed_updated = Signal(list)                # diff items
    queued_message_dispatched = Signal(str)             # prompt
```
- Subscribes asynchronously to `AsyncEventBus` (`SubagentLifecycleEvent`, `TaskStatusChangedEvent`, `TimerFiredEvent`, etc.).
- Safely emits Qt signals on the main thread via queued connections.

### 6.2 Queued Messages Queue
- Maintained inside `UIStateManager` per session: `queued_prompts: list[str]`.
- When user submits prompt:
  - If `session.is_in_flight == True`: append to `queued_prompts` and update `QueuedMessagesWidget`.
  - If `session.is_in_flight == False`: immediately dispatch generation worker.
- When `in_flight` state transitions from `True` to `False`:
  - If `queued_prompts` is non-empty, pop first item and dispatch.

### 6.3 Data Schemas
`SessionRecord` in `atbmind_core/storage/schemas.py`:
```python
class SessionRecord(BaseModel):
    session_id: str
    title: str = "新对话"
    workspace_name: str = "ATBMind"     # Project / Workspace identifier
    is_pinned: bool = False              # Pinned to top
    active_role_id: Optional[str] = None
    active_plugin_id: Optional[str] = None
    plugin_state: Dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
```

---

## 7. Error Handling & Edge Cases

1. **Zero-width Splitter Collapse**:
   - Prevented via `setChildrenCollapsible(False)` and minimum widths (`200px` left, `460px` center, `240px` right).
2. **Missing Workspace Name**:
   - Defaults to `"ATBMind"` or Git repository basename if unassigned.
3. **Queue Reentrancy**:
   - Protected against multiple triggers; queued items are popped atomically on main thread.
4. **Disconnection or Headless EventBus**:
   - If `AsyncEventBus` is absent or uninitialized, `EventBusQtBridge` falls back to direct UI signal invocations without crashing.

---

## 8. Verification & Testing Strategy

1. **`test_event_bus_qt_bridge.py`**:
   - Verify `EventBusQtBridge` receives `SubagentLifecycleEvent` and converts it into `subagent_lifecycle_changed` Qt signal on the main thread.
2. **`test_navigation_sidebar_antigravity.py`**:
   - Test rendering of Pinned section vs Project tree.
   - Test `Pin / Unpin` toggle and relative timestamp formatting.
3. **`test_agent_prompt_dock.py`**:
   - Test message queuing when session is in flight.
   - Test edit, delete, and send-now actions for queued messages.
   - Test model dropdown selection and clear/submit signals.
4. **`test_inspector_panel.py`**:
   - Test accordion expand/collapse logic and section item insertion.
   - Test subagent status updates (running spinner vs completed checkmark).
   - Test skills list rendering.
5. **`test_atbmind_3_pane_main_window.py`**:
   - Test complete 3-pane `QSplitter` assembly.
   - Test sidebar toggle (`Cmd+B`) and inspector toggle (`Cmd+Shift+I`).
   - Test session switching and breadcrumb path synchronization.
