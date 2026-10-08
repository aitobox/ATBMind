# Specification: Issue #72 - ContextCompactionMiddleware

## 1. Overview & Context
- **Issue**: [#72](https://github.com/aitobox/ATBMind/issues/72)
- **Parent Epic**: [#69](https://github.com/aitobox/ATBMind/issues/69) (Octop Architecture Adoption Phase 2)
- **Step**: Step 3 of 4
- **Objective**: Implement `ContextCompactionMiddleware` for long-running agent loops to monitor token budgets, protect system prompts and recent interactions, and fold middle history into compact summaries `[Conversation Summary: ...]`.

## 2. Architecture & Design Details

### 2.1 Middleware Interface (`atbmind_core/harness/middleware/compaction.py`)
```python
class ContextCompactionMiddleware:
    def __init__(
        self,
        max_tokens_budget: int = 4000,
        keep_recent_turns: int = 3,
        summarize_fn: Optional[Callable[[List[AgentMessage]], Awaitable[str]]] = None,
    ) -> None: ...

    def estimate_tokens(self, messages: List[AgentMessage], system_prompt: Optional[str] = None) -> int: ...
    def should_compact(self, messages: List[AgentMessage], system_prompt: Optional[str] = None) -> bool: ...
    async def compact(self, messages: List[AgentMessage], summarize_fn: Optional[Callable] = None) -> List[AgentMessage]: ...
    async def process_context(self, context: AgentContext) -> None: ...
```

### 2.2 Compaction Logic & Invariants
1. **Preservation**:
   - The initial `System Prompt` (or `messages[0]` if `role == Role.SYSTEM`) is ALWAYS preserved.
   - The most recent $K$ interactions (default 3 messages/turns) are ALWAYS preserved intact.
2. **Summarization**:
   - The middle segment (`messages[start_idx : -keep_recent]`) is folded into a single message containing `[Conversation Summary: ...]`.
   - Supports custom async `summarize_fn` or built-in fast extractive summarizer.
3. **Loop Integration**:
   - In `atbmind_core/harness/loop.py`, `agent_loop` inspects `config.middlewares` before calling `stream_client.stream_chat` each turn, running `mw.process_context(context)` if present.

## 3. Implementation Task List
- [x] Task 1: Module design & contract definitions (`atbmind_core/harness/middleware/compaction.py`)
- [x] Task 2: Unit tests & TDD test cases (`tests/test_context_compaction.py`)
- [x] Task 3: Core logic implementation (`ContextCompactionMiddleware` and `loop.py` integration)
- [x] Task 4: Integration verification & test suite pass (100% pytest pass across all tests)
- [x] Task 5: grill-me audit & stress-testing (token budget estimation, system prompt retention, turn boundary preservation)

## 4. Verification Plan
- `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_context_compaction.py -v`
- Full regression suite: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/`
