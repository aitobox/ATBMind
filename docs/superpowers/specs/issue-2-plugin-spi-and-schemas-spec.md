# Design Specification: Issue #2 实现标准插件接口 (ATBMindPlugin SPI) 与数据契约规范

- **Issue**: [#2](https://github.com/aitobox/ATBMind/issues/2)
- **Branch**: `agent/issue-2-plugin-spi-and-schemas`
- **Status**: Approved (Autonomous Decision Rule >= 90% confidence)
- **Author**: Antigravity Agent

---

## 1. Objective & Requirements

Define the standard Plugin Service Provider Interface (SPI) and data contract models for ATBMind. This decouples domain plugins (such as Draw, 3D, CAD) from the core middleware engine.

### Requirements:
1. `atbmind_core/plugins/schemas.py`:
   - `TemplateMetadata`: Comprehensive model for prompt/instruction templates.
   - `StructuredIntentDraft`: Standardized intermediate representation from Layer 1.
   - `WorkflowStep`: Standard node in a planned topological execution DAG (Layer 2 output).
   - `WorkflowResult`: Standard execution response from executing a workflow step (Layer 3 output).
2. `atbmind_core/plugins/base.py`:
   - `ATBMindPlugin`: Abstract base class implementing the SPI contracts:
     - `plugin_id`: str (property)
     - `version`: str (property)
     - `initialize(config: dict[str, Any]) -> None`
     - `get_templates() -> list[TemplateMetadata]`
     - `extract_context_entities(raw_input: Any) -> dict[str, Any]`
     - `get_domain_prompt_injection() -> str`
     - `execute_workflow_step(step: WorkflowStep, context: dict[str, Any]) -> WorkflowResult`
3. `atbmind_core/plugins/exceptions.py`:
   - `ATBMindPluginError`: Base exception for all plugin operations.
   - `PluginNotFoundError`: Requested plugin is not found in registry.
   - `PluginLoadError`: Plugin failed to import, instantiate, or initialize.
   - `PluginExecutionError`: Error occurred while executing a workflow step.
   - `PluginValidationError`: Schema or contract validation failure.

---

## 2. Acceptance Criteria & Verification Plan

- [x] All schemas implement Pydantic v2 with type hints and field descriptions.
- [x] `ATBMindPlugin` covers the entire lifecycle and execution interface.
- [x] Contract tests in `tests/test_plugin_schemas.py` verify that incomplete plugin subclasses raise `TypeError`.
- [x] Verification: `pytest tests/test_plugin_schemas.py` passes with 100% success.
