# Spec: Issue #35 - Implement Pluggable FooterDock & StylePopover

- **Status**: Approved (Phase 2 Design Specification)
- **Issue**: #35 ([UI-Component] Implement Pluggable FooterDock & StylePopover)
- **Branch**: `agent/issue-35-footer-dock-style-popover`
- **Reference**: `docs/superpowers/specs/2026-09-29-atbmind-ui-redesign-design.md` Section 3.3

---

## 1. Objectives & Architectural Context

Implement the complete pluggable bottom footer dock component and popup art style selector for the ATBMind desktop platform:
1. `apps/atbmind_desktop/widgets/style_popover.py`:
   - `StylePopover`: A dedicated popup grid menu displaying art styles (人像摄影, 电影写真, 中国风, 动漫, 3D渲染, 赛博朋克, 水墨画, 油画, 古典, 水彩画) matching the Doubao-style visual aesthetic and Apple HIG.
   - Emits `style_selected(style_id, style_name)` upon user selection.
2. `apps/atbmind_desktop/widgets/footer_dock.py`:
   - `FooterDock`: Pluggable bottom floating dock adhering to Apple HIG (16px border-radius, pure white background `#ffffff`, subtle border `#e5e5ea`).
   - Upper `PluginControlBar`:
     - Mode A (Plain text): Displays `[+ 载入插件]` button.
     - Mode B (ATBDraw loaded): Displays plugin capsule `[🖼️ 图像生成 (ATBDraw) ✕]`, model dropdown, aspect ratio dropdown, style button (anchoring `StylePopover`), and template dropdown.
   - Lower `PromptInputBar`:
     - Attachment button `[+]` supporting file picker dialog.
     - Drag-and-drop file support for images (`.png`, `.jpg`, `.jpeg`, `.webp`).
     - `AttachmentChip` rendering thumbnail image preview and `✕` removal button.
     - `AutoResizingTextEdit` (40px - 120px) with `Enter` to submit, `Shift+Enter` for newline.
     - Send button with busy/loading toggle (`set_busy(is_busy: bool)`: `↑` when idle, `⏹` when busy).
3. Test suite in `tests/test_footer_dock.py`: Comprehensive `pytest-qt` automated verification.

---

## 2. Component Design & API Specifications

### 2.1 StylePopover (`apps/atbmind_desktop/widgets/style_popover.py`)
- Inherits from `QFrame` (with `Qt.WindowType.Popup` or `Qt.WindowType.SubWindow | Qt.WindowType.FramelessWindowHint`).
- Layout:
  - Outer container with white background (`#ffffff`), `12px` rounded corners, subtle shadow/border (`1px solid #d2d2d7`).
  - Header title: "艺术风格 (Art Styles)" (12px, bold, `#86868b`).
  - Grid menu: `QGridLayout` displaying style items in 2 or 3 columns.
  - Style item button:
    - Displays icon (`📷`, `🎬`, etc.) and name (`人像摄影`, `电影写真`, etc.).
    - Padding: `6px 12px`, border-radius `8px`, hover background `#f2f2f7`.
    - Active item indicator: highlighted blue border or bold label.
- Signals:
  - `style_selected = Signal(str, str)` (style_id, style_name)
- Public Methods:
  - `show_at_widget(anchor_widget: QWidget)`: Computes global geometry and positions the popover neatly above or adjacent to `anchor_widget`.
  - `set_selected_style(style_id: str)`: Updates visual selection indicator.

### 2.2 AttachmentChip (`apps/atbmind_desktop/widgets/footer_dock.py`)
- Displays:
  - Thumbnail: Loads `QPixmap(file_path)` scaled to `20x20` with aspect ratio preserved, rounded corners, or fallback icon if unreadable.
  - File name: Truncated to max 20 chars if too long.
  - Delete button: `✕` emitting `remove_requested`.

### 2.3 AutoResizingTextEdit (`apps/atbmind_desktop/widgets/footer_dock.py`)
- Dynamic height calculation based on `document().size().height()`, bounded by `min_height=40` and `max_height=120`.
- Key handling:
  - `Enter` / `Return` without Shift -> emit `submit_pressed`.
  - `Shift+Enter` -> insert newline.
- Drag & Drop:
  - `dragEnterEvent` & `dropEvent`: Accept file drops containing image files (`.png`, `.jpg`, `.jpeg`, `.webp`), emitting signal or passing to parent `FooterDock.set_attachment()`.

### 2.4 FooterDock (`apps/atbmind_desktop/widgets/footer_dock.py`)
- Container:
  - Floating box with `#ffffff` background and `#e5e5ea` border, radius `16px`.
- Plugin Control Bar:
  - `load_plugin_btn`: Shows menu on click to select ATBDraw.
  - When ATBDraw loaded: shows capsule button (click unloads), `model_combo`, `ratio_combo`, `style_btn`, `template_combo`.
  - `style_btn`: Clicking opens `StylePopover`.
- Prompt Input Bar:
  - `attach_btn`: Opens `QFileDialog.getOpenFileName`.
  - Drag-and-drop: Dropping image files onto input bar or dock sets attachment.
  - `chip_container`: Houses `AttachmentChip`.
  - `text_edit`: AutoResizingTextEdit instance.
  - `send_btn`:
    - When idle: `↑`, blue `#0071e3`. Emits `submit_requested` if prompt or attachment present.
    - When busy: `⏹`, dark neutral or `#ff3b30`. Emits `stop_requested` if clicked.
- Public API:
  - `load_plugin(plugin_id: str, state: Optional[dict] = None)`
  - `unload_plugin()`
  - `get_plugin_state() -> Dict[str, Any]`
  - `set_plugin_state(state: Dict[str, Any])`
  - `set_attachment(file_path: Optional[str])`
  - `clear_attachment()`
  - `get_attachment() -> Optional[str]`
  - `set_prompt_text(text: str)`
  - `get_prompt_text() -> str`
  - `set_busy(busy: bool)`
  - `is_busy() -> bool`
- Signals:
  - `submit_requested = Signal(str, str, dict)` (prompt, attachment_path, plugin_state)
  - `plugin_changed = Signal(str, dict)` (plugin_id, plugin_state)
  - `stop_requested = Signal()`
  - `attachment_changed = Signal(str)`

---

## 3. Verification Plan

1. Automated pytest-qt test suite in `tests/test_footer_dock.py`:
   - `test_footer_dock_plain_text_mode`: Verify default controls and visibility.
   - `test_footer_dock_load_and_unload_plugin`: Verify ATBDraw capsule, combos, and state.
   - `test_style_popover_selection`: Verify popover displays styles and selection updates button and emits signals.
   - `test_attachment_chip_and_clear`: Verify setting attachment, thumbnail rendering, and clear button.
   - `test_auto_resizing_text_edit`: Verify height growth with multiline text and keypresses.
   - `test_submit_signal_emission`: Verify `submit_requested` payload with prompt, attachment, and plugin state.
   - `test_busy_toggle`: Verify send button appearance and stop signal emission when busy.
   - `test_drag_and_drop_attachment`: Verify drag and drop event handling sets attachment chip.
2. Full test suite verification:
   ```bash
   conda run -n ATBMind python -m pytest tests/
   ```
