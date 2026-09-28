# Implementation Plan: Issue #4 实现兼容 OpenAI 协议的统一大模型客户端 (支持云端与 Ollama)

- **Issue**: [#4](https://github.com/aitobox/ATBMind/issues/4)
- **Branch**: `agent/issue-4-openai-compat-llm-client`
- **Spec**: `docs/superpowers/specs/issue-4-openai-compat-llm-client-spec.md`
- **Status**: Ready for execution

---

## Tasks Breakdown

### Task 1: Write TDD LLM Client Tests
- File: `tests/test_llm_client.py`
- Test cases:
  1. `test_client_initialization`: Checks default and custom initialization from parameters or `LLMConfig`.
  2. `test_sync_chat_completion`: Mock httpx Transport returning standard 200 response, verify message extraction.
  3. `test_async_chat_completion`: Mock async httpx Transport and test `achat_completion`.
  4. `test_structured_json_clean_and_parse`: Test `generate_structured_json` with clean JSON, raw text with markdown fences, and Pydantic schema validation.
  5. `test_retry_mechanism_on_transient_error`: Mock httpx transport to fail twice with HTTP 503 / ConnectTimeout, succeed on 3rd attempt, verifying exponential backoff retries.
  6. `test_max_retries_exceeded_error`: Mock transport to consistently fail, verify `LLMConnectionError` / `LLMResponseError` is raised after max retries.
  7. `test_invalid_json_handling`: Verify `LLMJSONParseError` when output cannot be parsed as JSON.

### Task 2: Implement OpenAICompatClient & Exceptions
- File: `atbmind_core/engine/llm_client.py`
- Implement:
  - Custom exceptions (`LLMClientError`, `LLMConnectionError`, `LLMResponseError`, `LLMJSONParseError`)
  - `clean_json_text(text: str) -> str` utility
  - `OpenAICompatClient` class supporting sync and async HTTP calls, retries, and structured JSON parsing.

### Task 3: Verification & Test Execution
- Run `PYTHONPATH=. pytest tests/test_llm_client.py`
- Run full test suite: `PYTHONPATH=. pytest tests/`
