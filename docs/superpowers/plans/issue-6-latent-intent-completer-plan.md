# Implementation Plan: Issue #6 实现通用潜需求意图补全引擎 (Latent Intent Completer)

- **Issue**: [#6](https://github.com/aitobox/ATBMind/issues/6)
- **Branch**: `agent/issue-6-latent-intent-completer`
- **Spec**: `docs/superpowers/specs/issue-6-latent-intent-completer-spec.md`
- **Status**: Ready for execution

---

## Tasks Breakdown

### Task 1: Write TDD Completer Tests
- File: `tests/test_completer.py`
- Test cases:
  1. `test_intent_completer_basic`: Mock LLM returning valid JSON for "瘦一点", verify `StructuredIntentDraft` fields (`request_id`, `plugin_id`, `intent_category`, `parameters` with slimming intensity).
  2. `test_context_entity_anchoring`: Verify detected entities in context (e.g. `person_0`, bounding box) are retained in `target_entities`.
  3. `test_async_intent_completion`: Verify `acomplete_intent` produces equivalent output asynchronously.
  4. `test_custom_domain_injection`: Verify prompt injection from plugin is included in system prompt passed to LLM.
  5. `test_fallback_on_llm_error`: Verify that when LLM fails or returns corrupted output, a fallback heuristic or clean draft is safely produced without crashing.

### Task 2: Implement IntentCompleter
- File: `atbmind_core/engine/completer.py`
- Implement:
  - `IntentCompleter` class accepting an `OpenAICompatClient`
  - System prompt formatting combining role, schema, domain prompt injection, and context entities
  - `complete_intent` and `acomplete_intent` methods
  - Fallback logic when parsing/validation encounters recoverable errors.

### Task 3: Verification & Test Execution
- Run `PYTHONPATH=. pytest tests/test_completer.py`
- Run full test suite: `PYTHONPATH=. pytest tests/`
