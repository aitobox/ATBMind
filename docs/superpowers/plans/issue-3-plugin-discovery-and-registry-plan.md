# Implementation Plan: Issue #3 实现插件发现、动态扫描与生命周期注册中心

- **Issue**: [#3](https://github.com/aitobox/ATBMind/issues/3)
- **Branch**: `agent/issue-3-plugin-discovery-and-registry`
- **Spec**: `docs/superpowers/specs/issue-3-plugin-discovery-and-registry-spec.md`
- **Status**: Ready for execution

---

## Tasks Breakdown

### Task 1: Write TDD Registry Tests
- File: `tests/test_plugin_registry.py`
- Test cases:
  1. `test_manual_registration_and_retrieval`: Test `register_plugin`, `get_plugin`, `list_plugins`, `unregister_plugin`.
  2. `test_duplicate_and_not_found_handling`: Test duplicate registration raises `PluginValidationError`, non-existent plugin raises `PluginNotFoundError`.
  3. `test_dynamic_directory_scan`: Create a temp directory with mock plugins and test `scan_directory`.
  4. `test_corrupted_plugin_fault_tolerance`: Create broken plugins (syntax error, non-ATBMindPlugin, exception in initialize) and verify registry catches and isolates them in `failed_plugins` without crashing other plugins.
  5. `test_entry_points_scan`: Mock `importlib.metadata.entry_points` to verify entry points discovery.
  6. `test_singleton_get_plugin_registry`: Verify `get_plugin_registry()` singleton behavior.

### Task 2: Implement Plugin Registry
- File: `atbmind_core/plugins/registry.py`
- Implement:
  - `PluginRegistry` class
  - Dynamic module loading with `importlib.util.spec_from_file_location` and `spec.loader.exec_module`
  - Entry points loading via `importlib.metadata.entry_points`
  - `get_plugin_registry(reset: bool = False) -> PluginRegistry`

### Task 3: Verification & Test Execution
- Run `PYTHONPATH=. pytest tests/test_plugin_registry.py`
- Run full test suite: `PYTHONPATH=. pytest tests/`
