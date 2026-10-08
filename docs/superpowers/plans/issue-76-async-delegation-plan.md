# Implementation Plan: Async Non-Blocking Delegation & Concurrent Dispatch

- **Issue**: [#76](https://github.com/aitobox/ATBMind/issues/76)
- **Branch**: `agent/issue-76-async-delegation`
- **Spec**: `docs/superpowers/specs/issue-76-async-delegation-spec.md`

---

## Task Breakdown & Verification Matrix

### Task 1: Write TDD test cases in `tests/test_async_delegation.py`
- **File**: `tests/test_async_delegation.py`
- **Steps**:
  1. Test synchronous delegation backward compatibility (`async_mode=False`).
  2. Test asynchronous non-blocking return with receipt and job status PENDING/RUNNING (`async_mode=True`).
  3. Test concurrent multi-specialist dispatch (multiple jobs running in parallel).
  4. Test event tagging with `speaker_role` and `origin_role` during streaming.
  5. Test job completion callback and status change to COMPLETED in `TeamJobTracker`.
  6. Test error handling when specialist fails (job status transitions to FAILED).
- **Verification Command**:
  `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_async_delegation.py` (Must fail initially).

### Task 2: Update `DelegateTaskInput` schema
- **File**: `atbmind_core/roles/delegation.py`
- **Steps**:
  1. Add `async_mode: bool = Field(False, description="是否以异步非阻塞模式派工...")`.

### Task 3: Refactor `DelegateTaskTool`
- **File**: `atbmind_core/roles/delegation.py`
- **Steps**:
  1. Accept `job_tracker: Optional[TeamJobTracker] = None` and `completion_callback: Optional[Callable] = None`.
  2. Implement `_run_subagent_coro` encapsulating subagent execution, event forwarding with `speaker_role`, error trapping, and job completion.
  3. In `execute`:
     - Register job via `job_tracker.submit_job(...)`.
     - If `async_mode`: start background `asyncio.create_task` and immediately return dispatch confirmation.
     - If not `async_mode`: await execution directly.

### Task 4: Integrate `job_tracker` in `RobotTeam`
- **File**: `atbmind_core/roles/team.py`
- **Steps**:
  1. Initialize `self.job_tracker = job_tracker or TeamJobTracker()`.
  2. Pass `job_tracker=self.job_tracker` to `DelegateTaskTool` in `create_coordinator_session`.

### Task 5: Verify full test suite
- **Verification Command**:
  `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/`
  Ensure all 364+ tests pass.

### Task 6: Audit with grill-me and hand off to code review
- **Steps**:
  1. Verify zero regression in existing delegation tests (`test_roles_delegation.py`, `test_coordinator_rules.py`).
  2. Transition to `reviewing` and trigger `atb-github-code-reviewer`.
