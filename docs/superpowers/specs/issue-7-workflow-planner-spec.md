# Design Specification: Issue #7 实现通用模板匹配与拓扑工作流规划器 (Workflow Planner)

- **Issue**: [#7](https://github.com/aitobox/ATBMind/issues/7)
- **Branch**: `agent/issue-7-workflow-planner`
- **Status**: Approved (Autonomous Decision Rule >= 90% confidence)
- **Author**: Antigravity Agent

---

## 1. Objective & Requirements

Implement Layer 2 of the ATBMind core pipeline: `WorkflowPlanner` in `atbmind_core/engine/planner.py`.
It matches a `StructuredIntentDraft` against candidate `TemplateMetadata` items, prevents LLM template ID hallucinations, resolves dependencies, performs topological sorting over the DAG, and outputs a deterministic `WorkflowPlan`.

### Core Mechanisms
1. **Candidate Binning**:
   - Filters `available_templates` matching `draft.intent_category` (or includes secondary templates) up to a configurable limit (`max_candidates=200`).
2. **Anti-Hallucination Filter**:
   - Any template ID returned by the LLM that is not in the canonical `template_map` is strictly stripped out.
3. **Dependency Expansion & DAG Topological Sort**:
   - Recursively resolves required prerequisite templates in `template.dependencies`.
   - Applies Kahn's algorithm / DFS topological sorting to guarantee prerequisites execute before dependents (e.g., `T_SHAPE_001` before `T_CLOTH_002`).
   - Raises `CyclicDependencyError` if a dependency cycle exists.
4. **Output Contract (`WorkflowPlan`)**:
   - `request_id: str`
   - `plugin_id: str`
   - `steps: List[WorkflowStep]` (1-indexed step order).

---

## 2. Acceptance Criteria & Verification Plan

- [x] Hallucinated template IDs are rejected.
- [x] Inverted template orders are corrected by DAG topological sorting.
- [x] Circular dependencies raise `CyclicDependencyError`.
- [x] Verification: `pytest tests/test_planner.py` passes 100%.
