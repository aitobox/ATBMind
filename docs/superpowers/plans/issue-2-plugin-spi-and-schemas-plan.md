# Implementation Plan: Issue #2 实现标准插件接口 (ATBMindPlugin SPI) 与数据契约规范

- **Issue**: [#2](https://github.com/aitobox/ATBMind/issues/2)
- **Branch**: `agent/issue-2-plugin-spi-and-schemas`
- **Spec**: `docs/superpowers/specs/issue-2-plugin-spi-and-schemas-spec.md`
- **Status**: Ready for execution

---

## Tasks Breakdown

### Task 1: Write TDD Contract Tests
- File: `tests/test_plugin_schemas.py`
- Test cases:
  1. `test_template_metadata_schema`: Validates instantiation, field constraints, serialization.
  2. `test_structured_intent_draft_schema`: Validates intent draft fields and defaults.
  3. `test_workflow_step_and_result`: Validates step definition and execution result models.
  4. `test_plugin_abstract_enforcement`: Tests that inheriting `ATBMindPlugin` without implementing all abstract methods raises `TypeError`.
  5. `test_concrete_plugin_implementation`: Verifies full concrete implementation works properly with all SPI methods.
  6. `test_plugin_exceptions_hierarchy`: Tests inheritance and error message propagation for custom exceptions.

### Task 2: Implement Exceptions Hierarchy
- File: `atbmind_core/plugins/exceptions.py`
- Classes:
  - `ATBMindPluginError`
  - `PluginNotFoundError`
  - `PluginLoadError`
  - `PluginExecutionError`
  - `PluginValidationError`

### Task 3: Implement Data Contract Schemas
- File: `atbmind_core/plugins/schemas.py`
- Pydantic v2 Models:
  - `TemplateMetadata`
  - `StructuredIntentDraft`
  - `WorkflowStep`
  - `WorkflowResult`

### Task 4: Implement ATBMindPlugin SPI Base Class
- File: `atbmind_core/plugins/base.py`
- Abstract base class `ATBMindPlugin` with abstract properties and methods.

### Task 5: Verify & Run Test Suite
- Run `PYTHONPATH=. pytest tests/test_plugin_schemas.py`
- Run full regression suite: `PYTHONPATH=. pytest tests/`
