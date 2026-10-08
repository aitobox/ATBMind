# Design Specification: Async Non-Blocking Delegation & Concurrent Dispatch

- **Issue**: [#76](https://github.com/aitobox/ATBMind/issues/76)
- **Parent Epic**: [#74](https://github.com/aitobox/ATBMind/issues/74)
- **Sequence**: Step 2 of 4 (AgentTeams Execution Layer)

---

## 1. Problem Context & Objectives
Previously, ATBMind's `DelegateTaskTool` executed subagent loops in a synchronous blocking fashion:
- The Coordinator had to wait for the specialist's full conversation loop to terminate before receiving a return value.
- The Coordinator was unable to dispatch multiple tasks in parallel to distinct experts during a single turn.
- Events emitted by the subagent only carried an `origin_role` tag rather than a unified `speaker_role` identity for multi-speaker broadcast.

This specification upgrades `DelegateTaskTool` to support `async_mode: bool = False`, integrating with `TeamJobTracker` for background task lifecycle management, event bubbling with `speaker_role` tags, and completion wake-up callbacks.

---

## 2. Architectural Design

### 2.1 Schema Upgrades
- `DelegateTaskInput`:
  - `role_id: str`: Target specialist ID.
  - `task_description: str`: Structured assignment specification.
  - `async_mode: bool = False`: If True, executes asynchronously in the background and returns a dispatch receipt immediately.

### 2.2 Integration with `TeamJobTracker`
- `DelegateTaskTool` accepts `job_tracker: Optional[TeamJobTracker] = None`. If not passed, it uses `team.job_tracker` if present, or instantiates one.
- `RobotTeam` initializes and manages `job_tracker = TeamJobTracker()`.

### 2.3 Dispatch Workflow
1. **Validation**: Check `role_id` exists in `RobotTeam`.
2. **Job Registration**: `job = self.job_tracker.submit_job(role_id=role_id, task_description=task_description)`.
3. **Execution Branch**:
   - If `async_mode` is True:
     - Launch `asyncio.create_task(self._run_subagent(...))` in the background.
     - Return immediate `ToolResult` with job ID and receipt confirmation.
   - If `async_mode` is False:
     - Await `self._run_subagent(...)` directly and return `compose_followup` result.
4. **Subagent Execution & Event Tagging**:
   - `job_tracker.start_job(job.job_id)`.
   - Each event emitted by `agent_loop` is augmented with `speaker_role = role_id` and `job_id = job.job_id`.
   - Forward event to `self.event_listener` if configured.
5. **Completion & Followup Wake-up**:
   - On completion: `job_tracker.complete_job(job.job_id, result=final_reply)`.
   - Compose followup via `compose_followup`.
   - If `completion_callback` is provided, invoke it with `(role_id, task_description, final_reply, followup)`.
   - If in `async_mode` and `event_listener` is registered, emit a notification `AgentEvent` with `followup_notification=True`.

---

## 3. Subtask Scope Creep Guard
Strictly isolate implementation to `atbmind_core/roles/delegation.py`, `atbmind_core/roles/team.py`, and `tests/test_async_delegation.py`.
Do NOT modify storage thread projections or desktop UI timeline widgets (those belong to Issue #77 and #78).

---

## 4. Implementation Task List

- [x] Task 1: Update DelegateTaskInput schema with async_mode field
- [x] Task 2: Refactor DelegateTaskTool to support background asyncio tasks, TeamJobTracker lifecycle, and speaker_role tagging
- [x] Task 3: Integrate job_tracker into RobotTeam and propagate to Coordinator session
- [x] Task 4: Write comprehensive tests in tests/test_async_delegation.py
- [x] Task 5: Run full pytest test suite and verify 100% pass
- [x] Task 6: Execute grill-me audit for async concurrency and error safety
