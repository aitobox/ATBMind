# Design Specification: TeamJobTracker & In-Flight Job Model

- **Issue**: [#75](https://github.com/aitobox/ATBMind/issues/75)
- **Parent Epic**: [#74](https://github.com/aitobox/ATBMind/issues/74)
- **Sequence**: Step 1 of 4 (AgentTeams Foundation)

---

## 1. Problem Context & Objectives
In multi-agent collaborative workflows (e.g. `RobotTeam` coordinator dispatching specialist tasks), there has been no centralized in-flight job tracking mechanism. When a coordinator delegates subtasks to specialists:
1. Progress and execution status cannot be queried in a structured manner.
2. Team member configurations or specialist deletions could theoretically happen while tasks are actively executing.
3. No in-memory thread-safe state hub exists to manage the full job lifecycle (submission, execution, completion, failure, cancellation).

This specification draws upon Octop's `TeamJobTracker` design patterns to establish an in-memory, thread-safe job state tracker in `atbmind_core/roles/jobs.py`.

---

## 2. Architecture & Data Structures

### 2.1 `TeamJobStatus` Enum
```python
from enum import Enum

class TeamJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

### 2.2 `TeamJob` Model
A dataclass or Pydantic model representing an individual task:
- `job_id`: str (UUID or generated stable ID)
- `role_id`: str (target specialist role ID)
- `task_description`: str (task prompt/spec)
- `team_id`: Optional[str] (optional team identifier, defaults to "default")
- `status`: TeamJobStatus (defaults to PENDING)
- `result`: Optional[str] (execution result payload)
- `error`: Optional[str] (error details if failed)
- `created_at`: float (timestamp, `time.time()`)
- `started_at`: Optional[float]
- `completed_at`: Optional[float]
- `metadata`: Dict[str, Any]

### 2.3 `TeamJobTracker` Class
Thread-safe manager guarded by `threading.RLock`:
- `submit_job(role_id: str, task_description: str, job_id: Optional[str] = None, team_id: Optional[str] = None, metadata: Optional[dict] = None) -> TeamJob`:
  Registers a new job in `PENDING` state.
- `start_job(job_id: str) -> TeamJob`:
  Transitions job from `PENDING` to `RUNNING`, sets `started_at`. Raises `ValueError` if job not found or not in valid state.
- `complete_job(job_id: str, result: str = "") -> TeamJob`:
  Transitions job from `RUNNING` (or `PENDING`) to `COMPLETED`, sets `completed_at` and `result`.
- `fail_job(job_id: str, error: str = "") -> TeamJob`:
  Transitions job to `FAILED`, sets `completed_at` and `error`.
- `cancel_job(job_id: str, reason: str = "") -> TeamJob`:
  Transitions job to `CANCELLED`, sets `completed_at` and `error`.
- `get_job(job_id: str) -> Optional[TeamJob]`:
  Retrieves a copy or reference of the job by ID.
- `list_active_jobs(role_id: Optional[str] = None, team_id: Optional[str] = None) -> List[TeamJob]`:
  Returns jobs in `PENDING` or `RUNNING` status, optionally filtered by role or team.
- `has_active_jobs(role_id: Optional[str] = None, team_id: Optional[str] = None) -> bool`:
  Fast boolean check for in-flight tasks.
- `is_role_busy(role_id: str) -> bool`:
  Convenience helper checking if a role has any active jobs.
- `busy_role_ids(team_id: Optional[str] = None) -> Set[str]`:
  Returns all role IDs currently engaged in active jobs.

---

## 3. Subtask Scope Creep Guard
Strictly isolate implementation to `jobs.py`, exports in `__init__.py`, and `test_team_jobs.py`.
Do NOT modify `DelegateTaskTool` or UI components in this subtask (those belong to Issue #76 and #78).

---

## 4. Implementation Task List

- [x] Task 1: Define TeamJobStatus enum and TeamJob data model in atbmind_core/roles/jobs.py
- [x] Task 2: Implement thread-safe TeamJobTracker with job lifecycle and roster lock methods
- [x] Task 3: Export models in atbmind_core/roles/__init__.py and integrate type annotations
- [x] Task 4: Write comprehensive unit test suite in tests/test_team_jobs.py
- [x] Task 5: Run full pytest suite and verify 100% test pass
- [x] Task 6: Execute grill-me audit for edge cases and concurrency safety
