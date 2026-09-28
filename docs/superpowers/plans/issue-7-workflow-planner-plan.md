# Implementation Plan: Issue #7 实现通用模板匹配与拓扑工作流规划器 (Workflow Planner)

- **Issue**: [#7](https://github.com/aitobox/ATBMind/issues/7)
- **Branch**: `agent/issue-7-workflow-planner`
- **Spec**: `docs/superpowers/specs/issue-7-workflow-planner-spec.md`
- **Status**: Ready for execution

---

## Tasks Breakdown

### Task 1: Add `WorkflowPlan` Schema & `CyclicDependencyError`
- Update `atbmind_core/plugins/schemas.py` with `WorkflowPlan` model.
- Update `atbmind_core/plugins/exceptions.py` with `CyclicDependencyError`.

### Task 2: Write TDD Planner Tests
- File: `tests/test_planner.py`
- Test cases:
  1. `test_anti_hallucination_filtering`: LLM proposes both valid (`T_SHAPE_001`) and hallucinated (`T_FAKE_999`) template IDs. Verify `T_FAKE_999` is dropped and only `T_SHAPE_001` remains.
  2. `test_topological_sort_order_correction`: `T_CLOTH_002` depends on `T_SHAPE_001`. LLM outputs `["T_CLOTH_002", "T_SHAPE_001"]`. Verify planner re-orders to `["T_SHAPE_001", "T_CLOTH_002"]`.
  3. `test_auto_dependency_expansion`: LLM selects `T_CLOTH_002` which depends on `T_SHAPE_001`. Verify `T_SHAPE_001` is automatically pulled into the workflow and scheduled first.
  4. `test_circular_dependency_detection`: `T_A` depends on `T_B` and `T_B` depends on `T_A`. Verify `CyclicDependencyError` is raised.
  5. `test_async_plan_workflow`: Verify `aplan_workflow` works asynchronously.

### Task 3: Implement WorkflowPlanner
- File: `atbmind_core/engine/planner.py`
- Implement:
  - Candidate filtering
  - LLM structured selection prompt
  - Topological sorting with cycle detection (`_resolve_and_sort_dag`)
  - `plan_workflow` and `aplan_workflow`

### Task 4: Verification & Test Execution
- Run `PYTHONPATH=. pytest tests/test_planner.py`
- Run full test suite: `PYTHONPATH=. pytest tests/`
