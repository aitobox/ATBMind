# Implementation Plan: Issue #37 - Assemble ATBMindMainWindow & UI State Coordinator

- **Issue**: #37 ([UI-Integration] Assemble ATBMindMainWindow & UI State Coordinator)
- **Branch**: `agent/issue-37-assemble-atbmindmainwindow`
- **Spec**: `docs/superpowers/specs/issue-37-main-window-assembly-spec.md`

---

### Task 1: UI State Coordinator
- **Files**:
  - `apps/atbmind_desktop/__init__.py`
  - `apps/atbmind_desktop/state.py`
- **Details**:
  - Implement `UIStateManager(QObject)` with Qt Signals (`active_session_changed`, `session_in_flight_changed`, `plugin_state_changed`).
  - Cache active session, loaded sessions, in-flight state tracking.

### Task 2: Auxiliary Dialogs
- **Files**:
  - `apps/atbmind_desktop/widgets/__init__.py`
  - `apps/atbmind_desktop/widgets/image_viewer.py`
  - `apps/atbmind_desktop/widgets/settings_dialog.py`
- **Details**:
  - `ImageViewerDialog`: Modal full-resolution viewer with smooth scaling, closes on `Esc`.
  - `SettingsDialog`: Form fields for Provider, Base URL, API Key (password mask toggle), Model, Temperature; reads/writes via `atbmind_core.config.save_app_config`.

### Task 3: Sidebar Widget
- **Files**:
  - `apps/atbmind_desktop/widgets/sidebar.py`
- **Details**:
  - `SidebarWidget(QWidget)`: Fixed 250px, `#f7f7f8` background, branding header.
  - `+ 新对话` button (Cmd+N).
  - Session list with title, time, active plugin badge (🎨), and in-flight spinner.
  - Context menu: Rename and Delete.
  - Bottom `⚙️ 设置` button emitting `open_settings_requested`.

### Task 4: Chat Stream View
- **Files**:
  - `apps/atbmind_desktop/widgets/chat_stream.py`
- **Details**:
  - `ChatStreamView(QWidget)`: Header bar (session title, plugin indicator badge `[💬 通用对话]` or `[🎨 ATBDraw: 图像生成]`, clear button).
  - Scroll area with smooth auto-scroll to bottom.
  - Message bubble items: `UserMessageItem`, `AssistantTextMessageItem`, `ErrorResultCard`.

### Task 5: Pluggable Footer Dock
- **Files**:
  - `apps/atbmind_desktop/widgets/footer_dock.py`
- **Details**:
  - Floating rounded white box style.
  - Upper `PluginControlBar`: `[+ 载入插件]` toggleable to loaded capsule `[🖼️ 图像生成 (ATBDraw) ✕]`, model dropdown, aspect ratio dropdown, style button, template dropdown.
  - Lower `PromptInputBar`: `+` attachment button, thumbnail Chip with removal, `AutoResizingTextEdit`, send button.

### Task 6: MainWindow Assembly & State Coordination
- **Files**:
  - `apps/atbmind_desktop/main_window.py`
- **Details**:
  - `ATBMindMainWindow(QMainWindow)`: Assembles `SidebarWidget` (left), `ChatStreamView` (top right), `FooterDock` (bottom right).
  - Connects all signals with `SessionStore` and `UIStateManager`:
    - Session switching (loads messages, restores plugin parameters).
    - Session creation (adds to store, updates sidebar, resets input).
    - Session deletion (cascades image cleanup, updates sidebar).
    - Session rename (updates store, updates sidebar, updates header).
    - Message submission (stores user message, renders bubble, clears prompt).
    - Settings launcher (opens `SettingsDialog`).

### Task 7: Desktop Entry Point
- **Files**:
  - `apps/atbmind_desktop/main.py`
- **Details**:
  - `main()` function: initializes `QApplication`, configures fonts and styles, instantiates and shows `ATBMindMainWindow`.

### Task 8: Test Suite & Verification
- **Files**:
  - `tests/test_main_window_assembly.py`
- **Details**:
  - Comprehensive `qtbot` integration tests:
    - Test `UIStateManager` state changes and signal emissions.
    - Test `SidebarWidget` actions (new session, select, rename, delete).
    - Test `ChatStreamView` message rendering and clear.
    - Test `FooterDock` plugin toggle and attachment handling.
    - Test `SettingsDialog` load and save.
    - Test `ATBMindMainWindow` complete end-to-end integration and session switching.
    - Run full repository test suite: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/`
