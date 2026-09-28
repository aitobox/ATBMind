# Design Specification: Issue #6 实现通用潜需求意图补全引擎 (Latent Intent Completer)

- **Issue**: [#6](https://github.com/aitobox/ATBMind/issues/6)
- **Branch**: `agent/issue-6-latent-intent-completer`
- **Status**: Approved (Autonomous Decision Rule >= 90% confidence)
- **Author**: Antigravity Agent

---

## 1. Objective & Requirements

Implement Layer 1 of the core ATBMind pipeline: `IntentCompleter` in `atbmind_core/engine/completer.py`.
It accepts colloquial, low-bandwidth user input (e.g., "把这个人变瘦一点") along with domain context from `plugin.extract_context_entities()`, injects `plugin.get_domain_prompt_injection()`, calls the LLM, and produces a strongly validated `StructuredIntentDraft`.

### Key Capabilities
1. **Dynamic Prompt Assembly**:
   - Injects domain-specific rules from `plugin.get_domain_prompt_injection()`.
   - Embeds context entities (e.g. detected persons, masks, canvas size) into system prompt.
   - Enforces unambiguous categorization and default parameter imputation.
2. **Synchronous & Asynchronous Execution**:
   - `complete_intent(user_prompt: str, plugin: ATBMindPlugin, context_entities: dict | None = None, request_id: str | None = None) -> StructuredIntentDraft`
   - `acomplete_intent(...) -> StructuredIntentDraft`
3. **Structured Validation & Fallback**:
   - Validates output using `StructuredIntentDraft` Pydantic model.
   - Preserves entity anchors in `target_entities`.
   - Fallback heuristic when LLM returns degraded data.

---

## 2. Acceptance Criteria & Verification Plan

- [x] Expands colloquial intent into structured parameters with default imputation.
- [x] Anchors detected context entities.
- [x] Comprehensive test suite in `tests/test_completer.py`.
- [x] Verification: `pytest tests/test_completer.py` passes 100%.
