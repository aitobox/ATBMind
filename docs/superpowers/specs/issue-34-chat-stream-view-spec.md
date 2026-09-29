# Specification: ChatStreamView with Message Bubbles & ErrorCard (Issue #34)

## 1. Overview
Issue #34 specifies the modular implementation of the central conversation stream in ATBMind Desktop (`ChatStreamView`), decomposing message bubbles into an isolated module (`apps/atbmind_desktop/widgets/message_bubble.py`), enhancing the header bar with inline session title editing, and implementing comprehensive `qtbot` unit tests in `tests/test_chat_stream.py`.

## 2. Requirements & Component Architecture

### 2.1 `apps/atbmind_desktop/widgets/message_bubble.py`
Modular message bubble components:
- `UserMessageItem(QFrame)`:
  - Right-aligned container with accent background (`#0071e3`) and white text (`#ffffff`), rounded corners (`14px`).
  - Optional top thumbnail chip if an image is attached. Displays filename and emoji indicator (`📎 {filename} (🔍 预览)`).
  - Emits `zoom_requested = Signal(str)` when the thumbnail preview is clicked.
- `AssistantTextMessageItem(QFrame)`:
  - Left-aligned container with light gray background (`#f2f2f7`) and dark text (`#1d1d1f`), rounded corners (`14px`).
  - Text selectable with mouse for copying responses. Word-wrapped cleanly.
- `ErrorResultCard(QFrame)`:
  - Soft red inline notification card (`#fff2f2`, border `1px solid #ffcdd2`, text `#d32f2f`, radius `10px`).
  - Displays failure message and an interactive `[↺ 重试]` button.
  - Emits `retry_requested = Signal()`.
- `LoadingIndicatorItem(QFrame)`:
  - Left-aligned pulsing / typing indicator (`💬 正在思考中...`) displayed during generation.
  - Can be cleanly removed once the assistant message arrives.

### 2.2 `apps/atbmind_desktop/widgets/chat_stream.py`
The main stream container:
- Re-exports `UserMessageItem`, `AssistantTextMessageItem`, `ErrorResultCard`, and `LoadingIndicatorItem` for full backwards compatibility.
- Retains `DrawResultCardItem` for ATBDraw before/after image comparisons.
- `ChatHeaderBar(QWidget)`:
  - Inline editable title: Double-clicking the title or pressing an edit action toggles to an inline `QLineEdit`, emitting `title_changed = Signal(str)` upon Enter / editing finished.
  - Plugin indicator badge: `[💬 通用对话]` (gray) or `[🎨 ATBDraw: 图像生成]` (blue accent).
  - Clear history button (`clear_requested = Signal()`).
- `ChatStreamView(QWidget)`:
  - Encapsulates `ChatHeaderBar` and a `QScrollArea`.
  - Maintains a vertical message layout with bottom stretch.
  - Smooth auto-scrolling to bottom on new message additions.
  - Public methods:
    - `set_session_info(title: str, active_plugin_id: Optional[str])`
    - `add_user_message(content: str, attachment_path: Optional[str] = None)`
    - `add_assistant_message(content: str)`
    - `add_loading_indicator(text: str = "正在思考中...")`
    - `remove_loading_indicator()`
    - `add_plugin_result(payload: Dict[str, Any])`
    - `add_error_card(error_message: str)`
    - `load_messages(messages: list[MessageRecord])`
    - `clear_messages()`
    - `scroll_to_bottom()`
  - Public signals:
    - `clear_history_requested = Signal()`
    - `refine_requested = Signal(str, str)`
    - `zoom_requested = Signal(str)`
    - `retry_requested = Signal()`
    - `title_changed = Signal(str)`

### 2.3 Unit Testing (`tests/test_chat_stream.py`)
Using `pytest-qt` (`qtbot`):
- `test_user_message_item_rendering_and_zoom`: Verifies right-aligned layout and `zoom_requested` signal on thumbnail click.
- `test_assistant_text_message_item`: Verifies left-aligned layout and text selection flag.
- `test_error_result_card_retry`: Verifies error styling and `retry_requested` signal on button click.
- `test_loading_indicator`: Verifies addition and removal of loading indicator.
- `test_chat_header_bar_inline_edit`: Verifies double-click or inline editing emits `title_changed`.
- `test_chat_stream_view_append_and_clear`: Verifies message append, `scroll_to_bottom`, signal propagation, and `clear_messages`.
- `test_chat_stream_load_messages`: Verifies bulk message restoration from `MessageRecord` list.

## 3. Autonomous Decision Rationale
- Confidence >= 90%:
  - Extracting bubble widgets to `apps/atbmind_desktop/widgets/message_bubble.py` separates visual item rendering from stream layout orchestration, improving readability and maintainability.
  - Retaining re-exports in `chat_stream.py` prevents breaking existing usages in `main_window.py` or existing tests.
  - Using a double-click / Enter pattern for inline title editing aligns with macOS native HIG patterns while maintaining keyboard accessibility.
