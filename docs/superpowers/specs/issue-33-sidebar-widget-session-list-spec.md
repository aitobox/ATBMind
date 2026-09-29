# Specification: SidebarWidget with Session List & Settings Action (Issue #33)

## 1. Overview & Objective
Build and harden the left navigation sidebar (`SidebarWidget`) for ATBMind adhering strictly to Apple Human Interface Guidelines (HIG). The component provides:
1. Application branding (`🧠 ATBMind`).
2. High-priority new session button (`+ 新对话`) with `Cmd+N` / `Ctrl+N` keyboard shortcut.
3. Chronological session list displaying session title, relative/formatted timestamp, and active plugin badge (`🎨` or `💬`).
4. Session-level asynchronous task execution indicator (animated spinner for in-flight tasks).
5. Context menu on session rows providing "重命名 (Rename)" and "删除会话 (Delete)" actions.
6. Bottom toolbar with "⚙️ 设置 (Settings)" button triggering global settings modal.

---

## 2. Architectural Design & Components

### 2.1 Component Hierarchy
```
SidebarWidget (QWidget, fixed width: 250px)
├── Header Layout (QHBoxLayout)
│   └── Branding Label ("🧠 ATBMind", 16px bold)
├── New Session Button (QPushButton, "+ 新对话", Cmd+N / Ctrl+N shortcut)
├── Session List (QListWidget, custom context menu enabled)
│   └── QListWidgetItem -> SessionItemWidget (QWidget)
│       ├── Plugin Badge (QLabel, "🎨 " or "💬 ")
│       ├── Text Column (QVBoxLayout)
│       │   ├── Title Label (QLabel, 13px, weight 500, #1d1d1f)
│       │   └── Time Label (QLabel, 11px, #86868b)
│       └── In-Flight Spinner (LoadingSpinner / QLabel)
└── Bottom Toolbar (QHBoxLayout)
    ├── Settings Button (QPushButton, "⚙️ 设置", flat, hover state)
    └── Version / Status Label ("v0.1.0", subtle #86868b)
```

### 2.2 Apple HIG Styling Specifications
- **Widget Dimensions**: Width 250px, minimum width 220px, maximum width 280px.
- **Background Color**: `#f7f7f8` (macOS sidepane secondary background).
- **Dividers**: Right border `1px solid #e5e5ea`.
- **Item Margins**: 12px horizontal, 16px vertical for container.
- **List Item States**:
  - Rest: Transparent background, 8px border radius.
  - Hover: `#ebebeb`.
  - Selected: `#e5e5ea`.
- **New Session Button**:
  - Background `#ffffff`, border `1px solid #e5e5ea`, radius 8px, text `#0071e3`, font 13px semi-bold.
  - Hover state: Background `#f0f0f5`, border `#0071e3`.

### 2.3 Signals & Public Interface

#### Signals
- `new_session_requested`: Emitted when clicking "+ 新对话" or pressing shortcut.
- `session_selected(str)`: Emitted with `session_id` when clicking a session.
- `session_rename_requested(str, str)`: Emitted with `session_id` and `new_title`.
- `session_delete_requested(str)`: Emitted with `session_id` upon deletion confirmation.
- `open_settings_requested`: Emitted when clicking "⚙️ 设置".

#### Public Methods
- `set_sessions(sessions: List[SessionRecord], active_session_id: Optional[str] = None) -> None`: Populates or resets session items.
- `add_session(session: SessionRecord, select: bool = True) -> None`: Inserts a session at the top.
- `update_session(session: SessionRecord) -> None`: Updates text, badge, and time for an existing session.
- `remove_session(session_id: str) -> None`: Removes session from the list.
- `select_session(session_id: str) -> None`: Selects item without triggering re-emission loops.
- `set_in_flight(session_id: str, in_flight: bool) -> None`: Activates/deactivates the in-flight spinner for a specific session.
- `is_in_flight(session_id: str) -> bool`: Queries the in-flight state of a session.
- `create_context_menu(session_id: str, item: QListWidgetItem) -> QMenu`: Returns the contextual menu for testability and invocation.

---

## 3. Loading Spinner Design
An animated `LoadingSpinner(QWidget)`:
- Custom painting using `QPainter` with 8 radial lines or circular arc with varying opacity, rotating smoothly with a `QTimer` (default 80ms interval).
- Automatically starts timer when `in_flight == True` and stops/hides when `in_flight == False`.
- Native appearance matching macOS indeterminate progress indicators.

---

## 4. Test Strategy (`tests/test_sidebar_widget.py`)
Using `pytest-qt` (`qtbot`):
1. **Render & Layout**: Verify fixed width (250px), branding text, and buttons exist.
2. **New Session Request**: Test mouse click on `new_btn` and shortcut trigger.
3. **Session Population & Selection**: Add multiple sessions, verify list count, verify `session_selected` emission on item click.
4. **Session Update & Remove**: Verify title updates and item removal.
5. **In-Flight Spinner**: Test `set_in_flight` activates and stops spinner, query `is_in_flight`.
6. **Context Menu Actions**: Verify `create_context_menu` returns Rename and Delete actions, verify triggering them emits signals (with mocked/monkeypatched dialog inputs).
7. **Settings Action**: Verify clicking settings button emits `open_settings_requested`.
