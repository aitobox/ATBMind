# Design Specification: Issue #3 实现插件发现、动态扫描与生命周期注册中心

- **Issue**: [#3](https://github.com/aitobox/ATBMind/issues/3)
- **Branch**: `agent/issue-3-plugin-discovery-and-registry`
- **Status**: Approved (Autonomous Decision Rule >= 90% confidence)
- **Author**: Antigravity Agent

---

## 1. Objective & Requirements

Provide a zero-configuration, robust plugin lifecycle and discovery registry (`PluginRegistry`) that dynamically detects, instantiates, and manages `ATBMindPlugin` instances from:
1. Local directory convention (`plugins/` folder containing plugin packages with `plugin.py`).
2. Python `entry_points` (`atbmind.plugins` metadata group).

### Detailed Requirements
- **Registry API**:
  - `register_plugin(plugin: ATBMindPlugin, config: dict | None = None)`: Validates and initializes plugin. Raises `PluginValidationError` if invalid or duplicate.
  - `unregister_plugin(plugin_id: str)`: Removes plugin from active registry.
  - `get_plugin(plugin_id: str) -> ATBMindPlugin`: Returns plugin or raises `PluginNotFoundError`.
  - `list_plugins() -> list[str]`: Lists all active plugin IDs.
  - `get_all_plugins() -> dict[str, ATBMindPlugin]`: Returns dictionary of active plugins.
  - `scan_directory(dir_path: Path, config: dict | None = None)`: Dynamically scans directory for `plugin.py` or `.py` files.
  - `scan_entry_points(config: dict | None = None)`: Scans `importlib.metadata.entry_points(group="atbmind.plugins")`.
  - `scan_all(plugins_dir: Path | None = None, config: dict | None = None)`: Combines directory and entry points scan.
  - Fault tolerance: Any broken or corrupted plugin module must be recorded in `failed_plugins: dict[str, str]` without interrupting other plugins.
  - Singleton helper: `get_plugin_registry() -> PluginRegistry`.

---

## 2. Acceptance Criteria & Verification Plan

- [x] Correctly discovers and instantiates valid plugins.
- [x] Isolates broken plugins, logs error, and registers valid ones.
- [x] Comprehensive test suite in `tests/test_plugin_registry.py`.
- [x] Verification: `pytest tests/test_plugin_registry.py` passes 100%.
