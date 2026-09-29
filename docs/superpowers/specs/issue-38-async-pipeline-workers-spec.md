# Issue #38 Specification: GenerationWorker, TitleWorker & End-to-End Multi-turn Flow

- **Issue**: #38 `[Async-Pipeline] Implement GenerationWorker, TitleWorker & End-to-End Multi-turn Flow`
- **Branch**: `agent/issue-38-async-pipeline-workers`
- **Status**: Approved (Autonomous Decision >= 90% Confidence)
- **Date**: 2026-09-29

---

## 1. Objective
Implement asynchronous background `QThread` worker classes (`GenerationWorker` and `TitleWorker`) in `apps/atbmind_desktop/workers.py`, wire them into `ATBMindMainWindow` adhering to the main-thread single-writer persistence model, support non-blocking session switching during active generation, support the multi-turn image refinement loop (`[↺ 以此结果微调]`), and provide comprehensive `pytest-qt` end-to-end verification in `tests/test_atbmind_desktop.py`.

---

## 2. Architecture & Component Contracts

### 2.1 `apps/atbmind_desktop/workers.py`

#### A. `GenerationWorker(QThread)`
Bound to a specific `session_id` and execution context so the user can freely switch sessions while generation proceeds in the background.

- **Signals**:
  - `progress_updated = Signal(str, str)` — `(session_id, status_message)`
  - `finished = Signal(str, object, str)` — `(session_id, report, image_path)`
  - `text_finished = Signal(str, str)` — `(session_id, reply_text)`
  - `failed = Signal(str, str)` — `(session_id, error_message)`

- **Execution Modes**:
  1. **Plugin Mode (`active_plugin_id == "draw"`)**:
     - Emits `progress_updated(session_id, "Layer 1: 正在解析人像意图...")`
     - Extracts context entities via `plugin.extract_context_entities({"image_path": attachment_path, "prompt": prompt})`
     - Runs `IntentCompleter.complete_intent(...)` to obtain `StructuredIntentDraft`
     - Emits `progress_updated(session_id, "Layer 2: 正在编排修图工作流...")`
     - Runs `WorkflowPlanner.plan_workflow(...)` to obtain `WorkflowPlan` (respecting user-selected `template_id` in `plugin_state` when specified)
     - Emits `progress_updated(session_id, "Layer 3: 正在渲染精修图像...")`
     - Runs `SlotDispatcher.dispatch_workflow(...)` with `plugin_state` overrides
     - Persists resulting `image_bytes` (or fallback valid PNG) to `generated_images_dir / "{uuid}.png"`
     - Emits `finished(session_id, report, saved_image_path)` if `report.success` is `True`, otherwise emits `failed(session_id, error_msg)`.
  2. **Plain-Text Mode (`active_plugin_id is None`)**:
     - Emits `progress_updated(session_id, "正在生成回复...")`
     - Queries `llm_client.chat_completion(messages)` (or fast offline fallback when no API key is configured and no custom `llm_client` is injected)
     - Emits `text_finished(session_id, reply_text)` on success, or `failed(session_id, error_msg)` on exception.

#### B. `TitleWorker(QThread)`
Bound to `session_id`, triggered on the first turn of a session to summarize the conversation into a concise 4-8 word/character title without blocking the main thread.

- **Signals**:
  - `title_generated = Signal(str, str)` — `(session_id, new_title)`

- **Behavior**:
  - Queries `llm_client.chat_completion` with a system prompt instructing a concise 4-8 word/character summary title without punctuation.
  - Falls back deterministically to a sanitized 4-8 character summary derived from `prompt` if offline or unconfigured.
  - Emits `title_generated(session_id, new_title)`.

---

### 2.2 `ATBMindMainWindow` Integration (`apps/atbmind_desktop/main_window.py`)

1. **Single-Writer SQLite Persistence**:
   - Workers never hold or write to `SessionStore`.
   - Main thread slots (`_on_worker_finished`, `_on_worker_text_finished`, `_on_worker_failed`, `_on_title_generated`) perform all `SessionStore` writes (`append_message`, `update_session_title`, `update_session_plugin_state`).
2. **Non-Blocking Multi-Session Execution**:
   - `handle_submit_request` marks `self.state_manager.set_in_flight(active_id, True)`, which updates the `SidebarWidget` spinner indicator (`⏳`) for that session.
   - Users can switch to another session (`switch_session`) or create a new session (`create_new_session`) while `GenerationWorker` continues running in the background.
   - When `GenerationWorker` completes:
     - The `MessageRecord` is appended to `SessionStore` under the worker's `session_id`.
     - `self.state_manager.set_in_flight(session_id, False)` clears the sidebar spinner.
     - If `self.state_manager.active_session_id == session_id`, the UI immediately appends the `DrawResultCardItem` / `AssistantTextMessageItem` / `ErrorResultCard` to `ChatStreamView`.
     - If the user is viewing a different session, `ChatStreamView` for the current session is undisturbed; switching back to `session_id` loads the newly persisted result card from `SessionStore`.
3. **Refinement Loop (`[↺ 以此结果微调]`)**:
   - Clicking `refine_btn` on `DrawResultCardItem` emits `refine_requested(after_path, "在此基础上：")`.
   - `handle_refine_request` attaches `after_path` into `FooterDock` (`AttachmentChip`) and prefills `"在此基础上："`.
   - Submitting the next turn passes `after_path` as the new `before_img` input to `GenerationWorker`, completing the multi-turn iterative retouching loop.
4. **Thread Lifecycle Safety**:
   - Active `QThread` instances are tracked per session and waited upon cleanly during `closeEvent` or session cleanup to prevent premature `QThread` destruction warnings.
