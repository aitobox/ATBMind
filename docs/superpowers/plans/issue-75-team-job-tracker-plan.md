# Implementation Plan: TeamJobTracker & In-Flight Job Model

- **Issue**: [#75](https://github.com/aitobox/ATBMind/issues/75)
- **Branch**: `agent/issue-75-team-job-tracker`
- **Spec**: `docs/superpowers/specs/issue-75-team-job-tracker-spec.md`

---

## Task Breakdown & Verification Matrix

### Task 1: Write TDD tests for TeamJobStatus, TeamJob, and TeamJobTracker
- **File**: `tests/test_team_jobs.py`
- **Steps**:
  1. Test status transitions (`PENDING` -> `RUNNING` -> `COMPLETED`, `PENDING` -> `RUNNING` -> `FAILED`, `PENDING` -> `CANCELLED`).
  2. Test invalid transitions (e.g., trying to start an already completed or failed job).
  3. Test query methods: `get_job`, `list_active_jobs`, `has_active_jobs`, `is_role_busy`, `busy_role_ids`.
  4. Test concurrency / multithreaded task submission and completion.
- **Verification Command**:
  `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_team_jobs.py` (Must fail initially before implementation).

### Task 2: Implement TeamJobStatus and TeamJob in atbmind_core/roles/jobs.py
- **File**: `atbmind_core/roles/jobs.py`
- **Steps**:
  1. Define `TeamJobStatus(str, Enum)` with statuses: `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`.
  2. Define `TeamJob` dataclass with fields: `job_id`, `role_id`, `task_description`, `team_id`, `status`, `result`, `error`, `created_at`, `started_at`, `completed_at`, `metadata`.

### Task 3: Implement TeamJobTracker in atbmind_core/roles/jobs.py
- **File**: `atbmind_core/roles/jobs.py`
- **Steps**:
  1. Use `threading.RLock` to synchronize job state changes.
  2. Implement `submit_job`, `start_job`, `complete_job`, `fail_job`, `cancel_job`.
  3. Implement `get_job`, `list_active_jobs`, `has_active_jobs`, `is_role_busy`, `busy_role_ids`.
  4. Implement `begin` / `end` / `is_busy` methods for roster locking interoperability.

### Task 4: Export components in atbmind_core/roles/__init__.py
- **File**: `atbmind_core/roles/__init__.py`
- **Steps**:
  1. Import and expose `TeamJobStatus`, `TeamJob`, `TeamJobTracker` in `__all__`.

### Task 5: Verify full test suite and zero regression
- **Verification Command**:
  `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/`
  Confirm all tests (existing + new) pass.

### Task 6: Audit with grill-me and hand off to code review
- **Steps**:
  1. Stress-test edge cases (invalid job IDs, concurrent access, empty strings).
  2. Transition state to `reviewing` and trigger `atb-github-code-reviewer`.
