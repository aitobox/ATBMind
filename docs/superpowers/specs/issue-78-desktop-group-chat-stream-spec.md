# Design Specification: Desktop Group Chat Concurrent Multi-Stream Demuxing (ChatStreamView)

- **Issue**: [#78](https://github.com/aitobox/ATBMind/issues/78)
- **Parent Epic**: [#74](https://github.com/aitobox/ATBMind/issues/74)
- **Sequence**: Step 4 of 4 (AgentTeams UI/UX Presentation Layer)

---

## 1. Problem Context & Objectives
When multiple team specialists run concurrently and stream tokens simultaneously into the desktop UI, the current `ChatStreamView` tracks only a single active bubble (`_current_speaker_bubble` and `_current_speaker_id`).
- Interleaved streaming tokens between multiple specialists cause repeated bubble fragmentation and jitter.
- The UI needs an active speaker routing map `_active_bubbles: dict[str, AssistantTextMessageItem]` to maintain independent active streaming bubbles per specialist.
- Header badges should render role-specific avatars and bracketed identity badges (e.g., 【主持人】, 【代码专家】, 【绘图专家】).
- When a specialist's stream terminates (`is_end=True`), its active bubble is finalized smoothly without jumping or flickering.

---

## 2. Architecture & Data Structures

### 2.1 Multi-Speaker Routing Map in `ChatStreamView`
- Maintain `_active_bubbles: Dict[str, AssistantTextMessageItem]`.
- In `append_speaker_delta(speaker_role_id, speaker_name, delta, speaker_avatar, is_start, is_end)`:
  1. If `is_start` or `speaker_role_id not in _active_bubbles`:
     - Create a new `AssistantTextMessageItem` for `speaker_role_id`.
     - Register into `_active_bubbles[speaker_role_id]`.
     - Insert into message layout.
  2. Else:
     - Retrieve existing `bubble = _active_bubbles[speaker_role_id]`.
     - Append `delta` to `bubble`.
  3. If `is_end`:
     - Pop `_active_bubbles.pop(speaker_role_id, None)`.
     - Reset `_current_speaker_bubble` if it was pointing to this bubble.
- In `clear_messages`:
  - `_active_bubbles.clear()`.

### 2.2 Role-Aware Avatar & Badge Formatting in `AssistantTextMessageItem`
- Role badge defaults:
  - `coordinator`: `("✦", "主持人")`
  - `coder`: `("💻", "代码专家")`
  - `draw_expert`: `("🎨", "绘图专家")`
  - `analyst`: `("📊", "分析专家")`
  - `reviewer`: `("🔍", "审查专家")`
- Badge text formatting:
  `{avatar} 【{display_name}】`
- Support clean text appending and auto-scrolling without layout disruption.

---

## 3. Implementation Task List

- [ ] Task 1: Update AssistantTextMessageItem with role badge dictionary and bracketed badge formatting
- [ ] Task 2: Refactor ChatStreamView to maintain _active_bubbles dictionary for multi-speaker stream routing
- [ ] Task 3: Write desktop component unit tests in tests/test_desktop_group_chat_stream.py
- [ ] Task 4: Run full pytest test suite and verify 100% pass
- [ ] Task 5: Execute grill-me audit for UI stability and concurrent token interleaving
