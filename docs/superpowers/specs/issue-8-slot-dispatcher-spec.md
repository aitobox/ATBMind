# Design Specification: Issue #8 实现通用槽位填充与执行调度器 (Slot Dispatcher)

- **Issue**: [#8](https://github.com/aitobox/ATBMind/issues/8)
- **Branch**: `agent/issue-8-slot-dispatcher`
- **Status**: Approved (Autonomous Decision Rule >= 90% confidence)
- **Author**: Antigravity Agent

---

## 1. Objective & Requirements

Implement Layer 3 of the ATBMind core pipeline: `SlotDispatcher` in `atbmind_core/engine/dispatcher.py`.
It binds parameters from `TemplateMetadata` defaults, `StructuredIntentDraft` parameters, and optional user drawer overrides into `WorkflowStep.slots`, sequentially invokes `plugin.execute_workflow_step()`, propagates step outputs through the execution context, and returns a transparent `WorkflowExecutionReport`.

### Core Mechanisms
1. **Hierarchical Slot Resolution (`fill_slots`)**:
   - Priority 1 (Lowest): `template.slot_definitions[slot]["default"]`
   - Priority 2: `step.slots` pre-populated by planner
   - Priority 3: `draft.parameters` matching slot keys + `target_entities`
   - Priority 4 (Highest): `user_overrides` from interactive side-drawer fine-tuning
   - Type coercion (`float`, `int`, `bool`, `str`).
2. **Sequential Pipeline Execution (`dispatch_workflow`)**:
   - Calls `plugin.execute_workflow_step(step, context)` for each step in `WorkflowPlan`.
   - Passes output from step $N$ into `context["previous_output"]` for step $N+1$.
   - Gracefully catches exceptions from plugins, recording `WorkflowResult(success=False, error_message=...)` without crashing the middleware.
3. **Structured Execution Report (`WorkflowExecutionReport`)**:
   - Tracks `success`, `total_execution_time_ms`, `step_results`, `executed_steps` (including bound slot values for UI display), and `final_output`.

---

## 2. Acceptance Criteria & Verification Plan

- [x] Accurately binds draft parameters and falls back to template defaults for unmentioned slots.
- [x] Captures single-step execution exceptions and marks workflow status accurately.
- [x] Supports side-drawer parameter re-execution overrides.
- [x] Verification: `pytest tests/test_dispatcher.py` passes 100%.
