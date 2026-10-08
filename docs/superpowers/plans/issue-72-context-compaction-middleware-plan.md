# Implementation Plan - Issue #72: ContextCompactionMiddleware

## Overview
Implement adaptive context compaction middleware to monitor token budgets, protect system prompt and recent turns, and compact intermediate dialogue history to avoid context overflow in long agent tasks.

## Proposed Changes

### 1. `atbmind_core/harness/middleware/compaction.py`
- Implement `ContextCompactionMiddleware`:
  - `max_tokens_budget: int = 4000`
  - `keep_recent_turns: int = 3`
  - `estimate_tokens(messages: List[AgentMessage], system_prompt: Optional[str] = None) -> int`
  - `should_compact(messages: List[AgentMessage], system_prompt: Optional[str] = None) -> bool`
  - `compact(messages: List[AgentMessage], summarize_fn: Optional[Callable] = None) -> List[AgentMessage]`
  - `process_context(context: AgentContext) -> None`
- Implement robust extractive summarizer for default compaction when LLM summarizer is not provided.

### 2. `atbmind_core/harness/middleware/__init__.py`
- Export `ContextCompactionMiddleware`.

### 3. `atbmind_core/harness/loop.py`
- In `agent_loop`:
  - In each turn before LLM call, inspect `config.middlewares` for `process_context(context)` and invoke it.

### 4. `tests/test_context_compaction.py`
- Unit tests:
  - `test_compaction_skip_when_under_budget`
  - `test_compaction_triggered_when_over_budget`
  - `test_system_prompt_and_recent_turns_preservation`
  - `test_custom_summarize_fn`
  - `test_loop_integration_with_compaction_middleware`

## Verification
- `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_context_compaction.py -v`
- Full regression suite: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/`
