# Implementation Plan: ChatStreamView with Message Bubbles & ErrorCard (Issue #34)

## Task Breakdown

### Task 1: Create Unit Test Suite for ChatStream & MessageBubbles (TDD Red)
- File: `tests/test_chat_stream.py`
- Test cases:
  - `test_user_message_item_rendering_and_zoom(qtbot, tmp_path)`: Verify right alignment, text wrapping, thumbnail display with valid image path, and `zoom_requested` signal emission on thumbnail button click.
  - `test_assistant_text_message_item(qtbot)`: Verify left alignment, background styling, word wrapping, and selectable text.
  - `test_error_result_card(qtbot)`: Verify soft red palette, error message display, and `retry_requested` signal on `[↺ 重试]` button click.
  - `test_loading_indicator_item(qtbot)`: Verify loading indicator display and custom text.
  - `test_chat_header_bar_inline_edit(qtbot)`: Verify session title rendering, double-click to edit, Enter key committing title rename, and `title_changed` signal.
  - `test_chat_stream_view_operations(qtbot)`: Verify `add_user_message`, `add_assistant_message`, `add_loading_indicator`, `remove_loading_indicator`, `add_error_card`, `clear_messages`, and `scroll_to_bottom`.
  - `test_chat_stream_load_messages(qtbot)`: Verify bulk loading of `MessageRecord` objects into user and assistant bubbles.

### Task 2: Implement `apps/atbmind_desktop/widgets/message_bubble.py`
- File: `apps/atbmind_desktop/widgets/message_bubble.py`
- Implement:
  - `UserMessageItem`: Right-aligned user bubble with optional thumbnail preview button emitting `zoom_requested`.
  - `AssistantTextMessageItem`: Left-aligned assistant bubble with selectable text.
  - `ErrorResultCard`: Soft red inline card with `[↺ 重试]` button emitting `retry_requested`.
  - `LoadingIndicatorItem`: Typing/thinking indicator with text label and pulsing dot representation.

### Task 3: Enhance `apps/atbmind_desktop/widgets/chat_stream.py`
- File: `apps/atbmind_desktop/widgets/chat_stream.py`
- Import and re-export items from `message_bubble.py`.
- Update `ChatHeaderBar`:
  - Replace static `QLabel` with inline-editable title widget (e.g. click/double-click toggles editable `QLineEdit` with Enter/esc shortcuts, or dedicated edit icon).
  - Emit `title_changed` signal.
- Update `ChatStreamView`:
  - Add `add_loading_indicator(text: str = "正在思考中...")` and `remove_loading_indicator()`.
  - Forward `title_changed` signal.
  - Ensure `scroll_to_bottom()` triggers smooth scroll.

### Task 4: Execute & Verify Test Suite (TDD Green)
- Run `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_chat_stream.py`.
- Fix any issues and ensure all tests pass.

### Task 5: Full Regression Testing & Code Verification
- Run `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/`.
- Ensure all 100+ tests pass with zero regressions.
