# Implementation Plan: Desktop Group Chat Concurrent Multi-Stream Demuxing (ChatStreamView)

- **Issue**: [#78](https://github.com/aitobox/ATBMind/issues/78)
- **Branch**: `agent/issue-78-desktop-group-chat-stream`
- **Spec**: `docs/superpowers/specs/issue-78-desktop-group-chat-stream-spec.md`

---

## Task Breakdown & Verification Matrix

### Task 1: Write TDD test cases in `tests/test_desktop_group_chat_stream.py`
- **File**: `tests/test_desktop_group_chat_stream.py`
- **Steps**:
  1. Test interleaved streaming from two specialists (`coder` and `designer`) without creating extra bubbles.
  2. Verify that `_active_bubbles` holds both bubbles concurrently while streaming.
  3. Verify that completing one specialist's stream removes only that specialist from `_active_bubbles`.
  4. Verify header badges render avatars and bracketed identity badges (e.g., `【主持人】`, `【代码专家】`, `【绘图专家】`).
  5. Verify `clear_messages` resets `_active_bubbles`.
- **Verification Command**:
  `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_desktop_group_chat_stream.py` (Must fail initially).

### Task 2: Update `AssistantTextMessageItem` in `apps/atbmind_desktop/widgets/message_bubble.py`
- **File**: `apps/atbmind_desktop/widgets/message_bubble.py`
- **Steps**:
  1. Add role-to-badge mapping:
     ```python
     ROLE_DEFAULT_BADGES = {
         "coordinator": ("✦", "主持人"),
         "coder": ("💻", "代码专家"),
         "draw_expert": ("🎨", "绘图专家"),
         "analyst": ("📊", "分析专家"),
         "reviewer": ("🔍", "审查专家"),
     }
     ```
  2. Format `badge_text` with bracketed role identity.

### Task 3: Refactor `ChatStreamView` in `apps/atbmind_desktop/widgets/chat_stream.py`
- **File**: `apps/atbmind_desktop/widgets/chat_stream.py`
- **Steps**:
  1. In `__init__`, initialize `self._active_bubbles: Dict[str, AssistantTextMessageItem] = {}`.
  2. Refactor `append_speaker_delta` to route deltas through `self._active_bubbles[speaker_role_id]`.
  3. Clean up `_active_bubbles` on `is_end=True` and in `clear_messages`.

### Task 4: Verify test suite and zero regression
- **Verification Command**:
  `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/`
  Ensure all tests pass.

### Task 5: Audit with grill-me and hand off to code review
- **Steps**:
  1. Verify smooth streaming without UI flashing.
  2. Transition to `reviewing` and trigger `atb-github-code-reviewer`.
