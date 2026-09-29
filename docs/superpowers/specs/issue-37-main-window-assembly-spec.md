# Spec: Issue #37 - Assemble ATBMindMainWindow & UI State Coordinator

- **Status**: Approved (Phase 2 Design Specification)
- **Issue**: #37 ([UI-Integration] Assemble ATBMindMainWindow & UI State Coordinator)
- **Branch**: `agent/issue-37-assemble-atbmindmainwindow`
- **Reference**: `docs/superpowers/specs/2026-09-29-atbmind-ui-redesign-design.md` Sections 2, 3 & 4

---

## 1. Objectives & Architectural Context

Implement the core presentation layer of the ATBMind desktop platform:
1. `apps/atbmind_desktop/state.py`: `UIStateManager` for tracking active session ID, cached sessions, plugin state, and in-flight background worker status.
2. `apps/atbmind_desktop/widgets/`: Modular, Apple HIG compliant PySide6 UI widgets:
   - `sidebar.py`: `SidebarWidget` (250px fixed width, branding, `+ 新对话` Cmd+N, session list with in-flight spinner, context menu for rename/delete, bottom settings button).
   - `chat_stream.py`: `ChatStreamView` (header bar with title and plugin badge, vertical scroll area, auto-scroll to bottom, user bubble, assistant bubble, error card).
   - `footer_dock.py`: `FooterDock` (floating container, upper `PluginControlBar` with ATBDraw capsule/model/ratio/style/template, lower `PromptInputBar` with attachment chip, auto-resizing text edit, send button).
   - `settings_dialog.py`: `SettingsDialog` (modal dialog for editing AppConfig LLM settings, masked API key, save/cancel).
   - `image_viewer.py`: `ImageViewerDialog` (modal previewer for full-size images, Esc to close).
3. `apps/atbmind_desktop/main_window.py`: `ATBMindMainWindow(QMainWindow)` assembling Sidebar, ChatStreamView, FooterDock, and coordinating session lifecycle (create, switch, delete, rename) with `SessionStore`.
4. `apps/atbmind_desktop/main.py`: Primary application entry point initializing `QApplication` and launching `ATBMindMainWindow`.
5. Automated test suite: `tests/test_main_window_assembly.py` ensuring full component assembly, signal-slot bindings, session switching, and plugin restoration.

---

## 2. Component Specifications

### 2.1 UIStateManager (`apps/atbmind_desktop/state.py`)
- Inherits from `QObject` to provide Qt Signals:
  - `active_session_changed = Signal(str)` (emits `session_id`)
  - `session_in_flight_changed = Signal(str, bool)` (emits `session_id, is_in_flight`)
  - `plugin_state_changed = Signal(str, str, dict)` (emits `session_id, plugin_id, state_dict`)
- State attributes:
  - `active_session_id: Optional[str]`
  - `sessions_cache: Dict[str, SessionRecord]`
  - `in_flight_sessions: Set[str]`
- Methods:
  - `set_active_session(session_id: Optional[str])`
  - `get_active_session() -> Optional[SessionRecord]`
  - `cache_session(session: SessionRecord)`
  - `remove_cached_session(session_id: str)`
  - `set_in_flight(session_id: str, in_flight: bool)`
  - `is_in_flight(session_id: str) -> bool`

### 2.2 SidebarWidget (`apps/atbmind_desktop/widgets/sidebar.py`)
- Background: `#f7f7f8`, Border Right: `1px solid #e5e5ea`, Fixed Width: `250px`.
- Branding header: Logo + "ATBMind" text (font-weight bold, 16px).
- Action button: `+ 新对话` (primary light blue or neutral highlight, shortcut `Cmd+N`).
- Session list: `QListWidget` or custom scrollable layout displaying items:
  - Title, formatted timestamp, active plugin icon (`🎨` if `draw`).
  - Animated spinner or `⏳` indicator when `is_in_flight(session_id)` is true.
  - Context menu on right-click: "重命名 (Rename)" and "删除会话 (Delete)".
- Bottom area: `⚙️ 设置` button emitting `open_settings_requested`.
- Signals:
  - `new_session_requested = Signal()`
  - `session_selected = Signal(str)` (session_id)
  - `session_rename_requested = Signal(str, str)` (session_id, new_title)
  - `session_delete_requested = Signal(str)` (session_id)
  - `open_settings_requested = Signal()`

### 2.3 ChatStreamView (`apps/atbmind_desktop/widgets/chat_stream.py`)
- Header bar:
  - Editable or label title displaying active session title.
  - Plugin indicator badge: `[💬 通用对话]` (neutral grey badge) or `[🎨 ATBDraw: 图像生成]` (blue badge).
  - Clear history button `[🗑️ 清空]` emitting `clear_history_requested(session_id)`.
- Scroll Area:
  - `QScrollArea` containing a vertical container with `addStretch(1)`.
  - Message items:
    - `UserMessageItem`: Right-aligned bubble (`#0071e3`, white text or neutral light blue), optional top attachment image thumbnail.
    - `AssistantTextMessageItem`: Left-aligned bubble (`#f2f2f7`, dark text `#1c1c1e`).
    - `ErrorResultCard`: Soft red card (`#fff2f2`, border `#ffcdd2`, text `#d32f2f`) with `[↺ 重试]` button.
  - Helper methods:
    - `add_user_message(content: str, attachment_path: Optional[str] = None)`
    - `add_assistant_message(content: str)`
    - `add_error_card(error_msg: str, on_retry=None)`
    - `clear_messages()`
    - `scroll_to_bottom()`

### 2.4 FooterDock (`apps/atbmind_desktop/widgets/footer_dock.py`)
- Container: Rounded floating box (border-radius: `16px`, background: `#ffffff`, border: `1px solid #e5e5ea`).
- Upper `PluginControlBar`:
  - Default: `[+ 载入插件]` button -> opens menu (option `ATBDraw (图像生成)`).
  - Loaded state (`draw`):
    - Capsule badge: `[🖼️ 图像生成 (ATBDraw) ✕]` (clicking `✕` unloads plugin).
    - Model dropdown (`Seedream 4.5`, `Flux.1`, `SDXL`, `Mock Adapter`).
    - Aspect ratio dropdown (`自动`, `1:1`, `16:9`, `9:16`, `3:4`).
    - Style button (shows current style, opens `StylePopover`).
    - Template dropdown (`智能全身显瘦塑形`, `双频原生磨皮`, `面部立体轮廓微雕`, `服装边缘防畸变锁定`).
- Lower `PromptInputBar`:
  - `[+]` attachment button (opens file picker dialog for images).
  - Attachment Chip (shows miniature thumbnail + file name + `✕` remove button).
  - Text Edit (`AutoResizingTextEdit`, auto-resizes between 40px and 120px, `Enter` sends, `Shift+Enter` inserts newline).
  - Send button (blue circular button).
- Signals:
  - `submit_requested = Signal(str, str, dict)` (prompt, attachment_path, plugin_state)
  - `plugin_changed = Signal(str, dict)` (plugin_id or "", plugin_state)
  - `attachment_selected = Signal(str)`

### 2.5 SettingsDialog (`apps/atbmind_desktop/widgets/settings_dialog.py`)
- Modal `QDialog`.
- Form layout:
  - Provider (QComboBox: OpenAI, DeepSeek, Ollama, Local).
  - Base URL (QLineEdit).
  - API Key (QLineEdit, masked as Password, with toggle reveal checkbox).
  - Model Name (QLineEdit).
  - Temperature (QDoubleSpinBox or QSlider, 0.0 - 1.0).
- Buttons: `保存 (Save)` and `取消 (Cancel)`.
- Updates `configs/config.yaml` using `save_app_config` and updates in-memory config.

### 2.6 ATBMindMainWindow (`apps/atbmind_desktop/main_window.py`)
- Window title: `ATBMind`.
- Geometry: `1200 x 780` minimum `1024 x 640`.
- Central widget split:
  - Left: `SidebarWidget` (250px).
  - Right: `QVBoxLayout` with `ChatStreamView` expanding, and `FooterDock` docked at bottom.
- Coordination Logic:
  - `init_session()`: On launch, loads sessions from `SessionStore.get_recent_sessions()`. If empty, creates initial session.
  - `on_new_session_requested()`: Calls `SessionStore.create_session()`, registers in `UIStateManager`, adds to sidebar, switches active session.
  - `on_session_selected(session_id)`: Loads `MessageRecord`s from `SessionStore.get_messages(session_id)`, populates `ChatStreamView`, updates header title & plugin badge, updates `FooterDock` plugin state from `SessionRecord.plugin_state`.
  - `on_session_delete_requested(session_id)`: Prompts confirmation, calls `SessionStore.delete_session(session_id)` (cascading file cleanup), updates sidebar, switches to adjacent session or creates new if list becomes empty.
  - `on_session_rename_requested(session_id, new_title)`: Updates title in `SessionStore`, updates sidebar item, updates chat header.
  - `on_submit_requested(prompt, attachment_path, plugin_state)`: Persists user message in `SessionStore`, renders user bubble in `ChatStreamView`, clears input box and attachment chip.
  - `on_open_settings_requested()`: Opens modal `SettingsDialog`.

### 2.7 Application Entry Point (`apps/atbmind_desktop/main.py`)
- Initializes `QApplication`.
- Configures application name, font, and palette.
- Instantiates and displays `ATBMindMainWindow`.
- Handles command line arguments and clean shutdown.

---

## 3. Verification Plan
- Unit & integration tests in `tests/test_main_window_assembly.py` via `pytest-qt`:
  - Test `UIStateManager` state transitions and signal emissions.
  - Test `SidebarWidget` item addition, selection, rename, delete, in-flight spinner.
  - Test `ChatStreamView` message appending, scrolling, clearing.
  - Test `FooterDock` plugin loading, parameter change, attachment chip.
  - Test `SettingsDialog` form population and save.
  - Test `ATBMindMainWindow` assembly, session creation, switching, deletion, message submission.
  - Test `apps/atbmind_desktop/main.py` entry point invocation.
- Command: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_main_window_assembly.py`
