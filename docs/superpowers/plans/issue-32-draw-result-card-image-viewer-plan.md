# Implementation Plan: [UI-Component] Implement DrawResultCard & ImageViewerDialog for ChatStream

- **Issue**: [#32](https://github.com/aitobox/ATBMind/issues/32)
- **Status**: Ready for Execution

## Task 1: Create `plugins/draw/ui/draw_card.py` & `plugins/draw/ui/__init__.py`
- Create `plugins/draw/ui/__init__.py` exporting `DrawResultCard`.
- Implement `DrawResultCard(QFrame)` in `plugins/draw/ui/draw_card.py`:
  - Signals: `zoom_requested(str)`, `save_requested(str)`, `refine_requested(str, str)`.
  - Side-by-side Before and After image boxes with 8px border radius and aspect ratio preservation.
  - Metadata: Template name badge (`🎨 ATBDraw: {template_name}`), elapsed time label (`耗时: {elapsed:.1f}s`).
  - Action buttons: `[🔍 放大查看]`, `[💾 另存为]`, `[↺ 以此结果微调]`.
  - Handle save action: emit `save_requested(image_path)` and provide fallback file dialog if needed.

## Task 2: Review and Verify `apps/atbmind_desktop/widgets/image_viewer.py`
- Ensure `ImageViewerDialog(QDialog)` properly fulfills all HIG and dialog requirements:
  - Clean modal dialog with smooth image scaling.
  - Esc keypress handler (`keyPressEvent`).
  - Close button.
  - Graceful fallback for non-existent image paths.

## Task 3: Update `apps/atbmind_desktop/widgets/chat_stream.py`
- Import `DrawResultCard` from `plugins.draw.ui.draw_card`.
- Retain alias `DrawResultCardItem = DrawResultCard` to maintain 100% backward compatibility with `tests/test_atbmind_desktop.py`.
- Ensure `ChatStreamView` seamlessly handles card insertion and signal connections.

## Task 4: Write Automated `qtbot` Tests in `tests/test_plugin_ui.py`
- Implement comprehensive tests covering:
  - `DrawResultCard` rendering with mock PNG files.
  - Signal emission for `zoom_requested`, `save_requested`, `refine_requested`.
  - Behavior when image files are missing or payload is empty.
  - `ImageViewerDialog` initialization, Esc key dismissal, and close button click.

## Task 5: Run Full Repository Verification
- Run `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/` and verify all tests pass.
