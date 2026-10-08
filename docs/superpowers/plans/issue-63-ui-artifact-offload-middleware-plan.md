# Implementation Plan: Issue #63 - UI Artifact 旁路中间件与大 Payload 剥离解耦

**Issue**: [#63 [octop-adoption] 实现 UI Artifact 旁路中间件与大 Payload 剥离解耦](https://github.com/aitobox/ATBMind/issues/63)  
**Spec**: [docs/superpowers/specs/issue-63-ui-artifact-offload-middleware-spec.md](file:///Users/brainzhang/work/aitobox/ATBMind/docs/superpowers/specs/issue-63-ui-artifact-offload-middleware-spec.md)  
**Branch**: `agent/issue-63-ui-artifact-offload-middleware`  

---

### Task 1: Module design & contract definitions
- **Files**:
  - `atbmind_core/harness/tools/base.py`
  - `atbmind_core/harness/types.py`
  - `atbmind_core/harness/__init__.py`
- **Actions**:
  1. Add `artifact: Optional[Dict[str, Any]] = None` to `ToolResult` dataclass.
  2. In `atbmind_core/harness/types.py`:
     - Re-export `ToolResult`
     - Implement `to_model_message(message: AgentMessage | ToolResult | Dict[str, Any]) -> Dict[str, Any]` which strips any `artifact` or extraneous internal metadata.
  3. Ensure `to_llm_dict()` on `AgentMessage` maintains pure control-plane payload without leaking `artifact`.

---

### Task 2: Unit tests & TDD test cases
- **Files**:
  - `tests/test_artifact_offload.py`
- **Actions**:
  1. Write tests for `ToolResult(content="...", artifact={"card": "data"})`.
  2. Write tests for `to_model_message()` verifying that `artifact` is never present in model messages.
  3. Write tests for `ArtifactOffloadMiddleware`:
     - Test large JSON string ($\ge 3000$ chars) with `"atbmind_ui": true` is offloaded: payload moved to `result.artifact`, `result.content` replaced with summary + `data_ref: "artifact"`.
     - Test small payload (< 3000 chars) is not offloaded.
     - Test payload without `atbmind_ui` is not offloaded even if $\ge 3000$ chars.
     - Test non-JSON string or error result is passed through unchanged without exception.
  4. Run tests and observe failures (red phase).

---

### Task 3: ArtifactOffloadMiddleware core logic & agent_loop integration
- **Files**:
  - `atbmind_core/harness/middleware/__init__.py`
  - `atbmind_core/harness/middleware/artifact_offload.py`
  - `atbmind_core/harness/loop.py`
- **Actions**:
  1. Create `atbmind_core/harness/middleware/` package.
  2. Implement `ArtifactOffloadMiddleware`:
     - `process_tool_result(self, result: ToolResult) -> ToolResult`
     - Detects `atbmind_ui` in JSON / dict.
     - Creates compact summary string with `data_ref: "artifact"`.
  3. In `atbmind_core/harness/loop.py`:
     - Support middleware in `AgentLoopConfig` (defaulting to `[ArtifactOffloadMiddleware()]`).
     - Pass `res.artifact` to `TOOL_CALL_END` event payload.
     - Pass `res.artifact` to `tool_msg.metadata["artifact"]`.
  4. Run `tests/test_artifact_offload.py` to confirm green phase.

---

### Task 4: Integration verification & full test suite pass
- **Command**:
  - `conda run -n ATBMind python -m pytest tests/`
- **Actions**:
  - Confirm all 338+ existing tests pass with zero regressions.
  - Verify `tests/test_artifact_offload.py` test coverage $\ge 95\%$.

---

### Task 5: grill-me audit & stress-testing
- **Actions**:
  - Audit boundary conditions (boundary at exactly 3000 chars, malformed JSON, unicode strings, nested dicts).
  - Verify that downstream tasks (#64, #65) are not scope-creeped.
  - Advance state to `reviewing`.
