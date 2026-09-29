# Specification: [UI-Component] Implement DrawResultCard & ImageViewerDialog for ChatStream

- **Issue**: [#32](https://github.com/aitobox/ATBMind/issues/32)
- **Status**: Draft -> Accepted
- **Author**: Antigravity Agent
- **Date**: 2026-09-29

## 1. Objective & Requirements

Provide a clean, decoupled PySide6 comparison card component (`DrawResultCard`) for the ATBDraw plugin and a modal full-resolution image viewer (`ImageViewerDialog`), conforming strictly to Apple Human Interface Guidelines and the ATBMind UI redesign design specifications (`docs/superpowers/specs/2026-09-29-atbmind-ui-redesign-design.md` Sections 3.2 & 3.4).

### Key Acceptance Criteria:
1. `plugins/draw/ui/draw_card.py` implements `DrawResultCard(QFrame)`:
   - Renders Before (original) and After (retouched) images side-by-side with 8px rounded corners and aspect ratio preservation.
   - Displays metadata bar: elapsed seconds, template name badge (`🎨 ATBDraw: {template_name}`).
   - Action buttons:
     - `[🔍 放大查看]`: Emits `zoom_requested(image_path)`.
     - `[💾 另存为]`: Emits `save_requested(image_path)` and provides standard fallback save dialog.
     - `[↺ 以此结果微调]`: Emits `refine_requested(image_path, prompt_prefix)` with `"在此基础上："`.
   - Signals: `zoom_requested = Signal(str)`, `save_requested = Signal(str)`, `refine_requested = Signal(str, str)`.
2. `apps/atbmind_desktop/widgets/image_viewer.py` provides `ImageViewerDialog(QDialog)`:
   - Centered high-resolution image viewing with smooth scaling.
   - Closes cleanly on `Esc` key press and on close button click.
3. `apps/atbmind_desktop/widgets/chat_stream.py`:
   - Integrates `DrawResultCard` from `plugins.draw.ui.draw_card`.
   - Maintains `DrawResultCardItem = DrawResultCard` alias for 100% backwards compatibility with `tests/test_atbmind_desktop.py`.
4. Automated `qtbot` tests in `tests/test_plugin_ui.py`:
   - Comprehensive test suite testing all signals, layouts, and dialog behaviors.

## 2. Component Design & Interfaces

### 2.1 `DrawResultCard` (`plugins/draw/ui/draw_card.py`)
```python
class DrawResultCard(QFrame):
    zoom_requested = Signal(str)
    save_requested = Signal(str)
    refine_requested = Signal(str, str)

    def __init__(self, payload: Dict[str, Any], parent: Optional[QWidget] = None) -> None: ...
```
- `payload` keys:
  - `before_img`: Local file path to original input image.
  - `after_img`: Local file path to generated/retouched image.
  - `elapsed_seconds`: Float seconds spent during generation.
  - `template_name`: Human-readable template title (e.g. `智能全身显瘦塑形`).

### 2.2 `ImageViewerDialog` (`apps/atbmind_desktop/widgets/image_viewer.py`)
```python
class ImageViewerDialog(QDialog):
    def __init__(self, image_path: str, parent: Optional[QWidget] = None) -> None: ...
```
- Esc key event handling: overrides `keyPressEvent(event: QKeyEvent)` to call `self.accept()`.

## 3. Verification Plan
- Unit & GUI tests in `tests/test_plugin_ui.py` using `pytest-qt` (`qtbot`).
- Full regression verification across existing test suites (`tests/test_atbmind_desktop.py` etc.).
