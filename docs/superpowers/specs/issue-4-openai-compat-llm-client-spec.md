# Design Specification: Issue #4 实现兼容 OpenAI 协议的统一大模型客户端 (支持云端与 Ollama)

- **Issue**: [#4](https://github.com/aitobox/ATBMind/issues/4)
- **Branch**: `agent/issue-4-openai-compat-llm-client`
- **Status**: Approved (Autonomous Decision Rule >= 90% confidence)
- **Author**: Antigravity Agent

---

## 1. Objective & Requirements

Implement a unified OpenAI-compatible LLM client (`OpenAICompatClient`) in `atbmind_core/engine/llm_client.py` using `httpx`. It standardizes chat completions and structured JSON extractions across commercial cloud APIs (OpenAI, DeepSeek, Doubao) and local providers (Ollama, vLLM).

### Detailed Architecture & Behaviors
1. **Connection & Configuration**:
   - `base_url`: e.g. `https://api.openai.com/v1`, `http://localhost:11434/v1`, `https://api.deepseek.com/v1`.
   - `api_key`: Optional or Bearer token header.
   - `model`: Model name string.
   - `temperature`: float (default 0.1 for high determinism).
   - `timeout`: float seconds.
   - `max_retries`: int retry count with exponential backoff on network errors or 5xx/429 status codes.
2. **Methods**:
   - Synchronous:
     - `chat_completion(messages, **kwargs) -> str`
     - `generate_structured_json(messages, schema=None, **kwargs) -> dict[str, Any]`
   - Asynchronous:
     - `achat_completion(messages, **kwargs) -> str`
     - `agenerate_structured_json(messages, schema=None, **kwargs) -> dict[str, Any]`
3. **Structured JSON Extraction**:
   - Passes `response_format={"type": "json_object"}` in payload.
   - Robust cleanup of markdown code fences (````json ... ````).
   - Validates using Pydantic model if `schema` is provided.
   - Custom exceptions: `LLMClientError`, `LLMConnectionError`, `LLMResponseError`, `LLMJSONParseError`.
4. **Resilience**:
   - Automatic retries on `httpx.TimeoutException`, `httpx.NetworkError`, 429, 500, 502, 503, 504.

---

## 2. Acceptance Criteria & Verification Plan

- [x] Works with any OpenAI-compatible endpoint.
- [x] Exponential backoff retry on simulated transient failures.
- [x] Markdown-wrapped JSON parsing and Pydantic schema validation.
- [x] Single and full test suite passes: `pytest tests/test_llm_client.py`.
