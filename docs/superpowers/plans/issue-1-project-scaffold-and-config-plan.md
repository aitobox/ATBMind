# Implementation Plan: Issue #1 搭建项目单仓工程骨架、配置管理与基础依赖

- **Issue**: [#1](https://github.com/aitobox/ATBMind/issues/1)
- **Branch**: `agent/issue-1-project-scaffold-and-config`
- **Spec**: `docs/superpowers/specs/issue-1-project-scaffold-and-config-spec.md`
- **Status**: Ready for execution

---

## Tasks Breakdown

### Task 1: Scaffolding Directory Skeleton & Requirements
- **Action**: Create core package directories and `__init__.py` markers:
  - `atbmind_core/`
  - `atbmind_core/plugins/`
  - `atbmind_core/engine/`
  - `atbmind_core/storage/`
  - `atbmind_core/utils/`
  - `plugins/`
  - `plugins/draw/`
  - `apps/`
  - `apps/atb_draw_desktop/`
  - `configs/`
  - `tests/`
- **Files**:
  - `requirements.txt`
  - `pytest.ini`

### Task 2: Base Configuration File
- **Action**: Create default configuration YAML:
  - File: `configs/config.yaml`
  - Content: Structured defaults for `server`, `llm`, `storage`, and `plugins`.

### Task 3: Test-Driven Development - Configuration Tests
- **Action**: Write comprehensive test suite in `tests/test_config.py`:
  - `test_default_config_loading`: Ensure `configs/config.yaml` loads with expected defaults.
  - `test_custom_config_loading`: Ensure loading from a custom YAML file works.
  - `test_env_override`: Ensure `ATBMIND_*` environment variables override YAML values.
  - `test_invalid_config_validation`: Ensure invalid types raise `ValidationError`.
  - `test_get_config_singleton`: Ensure `get_config()` caches and provides consistent instances.

### Task 4: Implement Configuration Subsystem
- **Action**: Implement `atbmind_core/config.py`:
  - Pydantic v2 schemas: `ServerConfig`, `LLMConfig`, `StorageConfig`, `PluginConfig`, `AppConfig`.
  - YAML file parsing with PyYAML.
  - Recursive or selective environment variable overrides (`ATBMIND_...`).
  - `load_config(config_path: str | Path | None = None) -> AppConfig`
  - `get_config(reload: bool = False) -> AppConfig`

### Task 5: Verification & Quality Gate
- **Action**:
  - Run `pytest tests/`
  - Run verification script: `python3 -c 'from atbmind_core.config import load_config; cfg = load_config(); print(cfg)'`
  - Verify zero lint/type regressions.
