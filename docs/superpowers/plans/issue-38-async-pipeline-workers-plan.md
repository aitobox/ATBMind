# Issue #38 Implementation Plan: GenerationWorker, TitleWorker & End-to-End Multi-turn Flow

- **Issue**: #38 `[Async-Pipeline] Implement GenerationWorker, TitleWorker & End-to-End Multi-turn Flow`
- **Spec**: `docs/superpowers/specs/issue-38-async-pipeline-workers-spec.md`
- **Branch**: `agent/issue-38-async-pipeline-workers`

---

## Task 1: Implement `GenerationWorker` & `TitleWorker` (`apps/atbmind_desktop/workers.py`)
1. Create `apps/atbmind_desktop/workers.py`:
   - Implement `GenerationWorker(QThread)`:
     - Signals: `progress_updated(str, str)`, `finished(str, object, str)`, `text_finished(str, str)`, `failed(str, str)`.
     - Support ATBDraw pipeline execution: Layer 1 (`IntentCompleter`), Layer 2 (`WorkflowPlanner`), Layer 3 (`SlotDispatcher` + `DrawPlugin`), saving resulting image bytes to `data/generated_images/{uuid}.png`.
     - Support plain-text chat mode via `OpenAICompatClient` with fast local fallback when API key is empty and no custom `llm_client` is provided.
     - Support cancellation/staleness flag (`cancel()`).
   - Implement `TitleWorker(QThread)`:
     - Signal: `title_generated(str, str)`.
     - Summarize first user prompt into a concise 4-8 word/character conversation title via `OpenAICompatClient` with deterministic fallback.

## Task 2: Wire Workers & Multi-Turn Pipeline into `ATBMindMainWindow` (`apps/atbmind_desktop/main_window.py`)
1. Update `ATBMindMainWindow`:
   - Track active workers (`_workers`) and session epochs (`_session_epochs`) to handle concurrent multi-session execution and safe cancellation on history clear / session delete.
   - In `handle_submit_request`:
     - Detect first turn in session and launch `TitleWorker`.
     - Set session in-flight state (`self.state_manager.set_in_flight(active_id, True)`).
     - Launch `GenerationWorker` bound to `active_id` and connect signals (`progress_updated`, `finished`, `text_finished`, `failed`).
   - Implement main-thread single-writer signal handlers:
     - `_on_generation_finished(session_id, report, image_path)`
     - `_on_text_generation_finished(session_id, reply_text)`
     - `_on_generation_failed(session_id, error_message)`
     - `_on_title_generated(session_id, new_title)`
   - Connect `ChatStreamView.retry_requested` to `handle_retry_request`.
   - Override `closeEvent` to wait for any running `QThread` workers cleanly.

## Task 3: Write End-to-End `pytest-qt` Tests (`tests/test_atbmind_desktop.py`)
1. Create `tests/test_atbmind_desktop.py` covering all acceptance criteria:
   - `test_generation_worker_draw_pipeline`: Direct `GenerationWorker` test verifying Layer 1 -> Layer 2 -> Layer 3 execution, image file creation in `generated_images/`, and `finished` signal emission.
   - `test_generation_worker_plain_text_and_failure`: Direct `GenerationWorker` test for `text_finished` and `failed` signals.
   - `test_title_worker_summary`: Direct `TitleWorker` test with mock LLM client and fallback mode.
   - `test_end_to_end_first_turn_title_and_draw_generation`: Full `ATBMindMainWindow` test verifying first-turn submission triggers `TitleWorker` (updating sidebar & header title) and `GenerationWorker` (persisting assistant `MessageRecord` and rendering `DrawResultCardItem`).
   - `test_non_blocking_session_switching_during_generation`: Full test verifying user can switch to Session B while Session A is generating; Sidebar shows spinner on Session A; completion writes to Session A without polluting Session B; switching back to Session A displays the completed `DrawResultCardItem`.
   - `test_multi_turn_refinement_loop`: Full test verifying clicking `[↺ 以此结果微调]` on `DrawResultCardItem` populates `FooterDock` attachment chip with generated `after_img` and prefills `"在此基础上："`, and submitting the second turn uses `after_img` as the new `before_img`.

## Task 4: Full Regression Suite Verification
1. Run `conda run -n ATBMind python -m pytest tests/` and confirm all existing 94 tests + new desktop tests pass 100%.
