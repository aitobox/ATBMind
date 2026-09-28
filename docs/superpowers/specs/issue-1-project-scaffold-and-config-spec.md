# Design Specification: Issue #1 搭建项目单仓工程骨架、配置管理与基础依赖

- **Issue**: [#1](https://github.com/aitobox/ATBMind/issues/1)
- **Branch**: `agent/issue-1-project-scaffold-and-config`
- **Status**: Approved (Autonomous Decision Rule >= 90% confidence)
- **Author**: Antigravity Agent

---

## 1. Objective & Scope

Establish the monorepo scaffold, foundational dependencies, configuration loader, and pytest test suite for **ATBMind** (Universal Prompt-to-Intent Middleware) according to the architecture defined in `docs/design/ATBMind-design.md`.

### Core Requirements
1. **Monorepo Directory Layout**:
   - `atbmind_core/`: Core middleware packages (`plugins/`, `engine/`, `storage/`, `utils/`).
   - `plugins/`: Pluggable domain plugins directory (with initial placeholder for `plugins/draw/`).
   - `apps/`: Application shells (such as `apps/atb_draw_desktop/`).
   - `configs/`: YAML configuration files (`configs/config.yaml`).
   - `tests/`: Automated test suite.
2. **Dependency Management**:
   - `requirements.txt`: Specifying FastAPI, Pydantic v2 (`pydantic>=2.5`), PyYAML, httpx, pytest, pytest-asyncio, PySide6.
3. **Configuration Subsystem (`atbmind_core/config.py`)**:
   - Pydantic models for structured, type-safe settings (`AppConfig`, `LLMConfig`, `ServerConfig`, `StorageConfig`, `PluginConfig`).
   - Hierarchical loading: Default values -> YAML file (`configs/config.yaml` or custom path) -> Environment variable overrides (`ATBMIND_*`).
   - Thread-safe `load_config(path: str | Path | None = None) -> AppConfig` and `get_config()`.
4. **Test Scaffold & Verification**:
   - `pytest.ini` configuring pythonpath and test discovery.
   - Comprehensive test cases in `tests/test_config.py` ensuring YAML parsing, env overrides, and validation error handling.

---

## 2. Architecture & Design Details

### 2.1 Configuration Schema Design

```python
class LLMConfig(BaseModel):
    provider: str = "openai"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o"
    temperature: float = 0.2
    timeout_seconds: float = 30.0
    max_retries: int = 3

class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False

class StorageConfig(BaseModel):
    db_path: str = "data/atbmind.db"
    in_memory: bool = False

class PluginConfig(BaseModel):
    plugins_dir: str = "plugins"
    enabled_plugins: list[str] = ["draw"]

class AppConfig(BaseModel):
    app_name: str = "ATBMind"
    version: str = "0.1.0"
    env: str = "development"
    server: ServerConfig = Field(default_factory=ServerConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    plugins: PluginConfig = Field(default_factory=PluginConfig)
```

### 2.2 Environment Variable Mapping

Environment variables prefixed with `ATBMIND_` will override YAML/default values:
- `ATBMIND_ENV` -> `app_config.env`
- `ATBMIND_DEBUG` -> `app_config.server.debug`
- `ATBMIND_HOST` -> `app_config.server.host`
- `ATBMIND_PORT` -> `app_config.server.port`
- `ATBMIND_LLM_BASE_URL` -> `app_config.llm.base_url`
- `ATBMIND_LLM_API_KEY` -> `app_config.llm.api_key`
- `ATBMIND_LLM_MODEL` -> `app_config.llm.model`
- `ATBMIND_DB_PATH` -> `app_config.storage.db_path`

---

## 3. Acceptance Criteria & Verification Plan

### Acceptance Criteria
- [x] Monorepo directory skeleton complete with all `__init__.py` files.
- [x] `requirements.txt` contains required dependencies.
- [x] `configs/config.yaml` provides ready-to-run defaults.
- [x] `atbmind_core/config.py` correctly parses YAML and applies environment variable overrides.
- [x] Pytest executes cleanly: `PYTHONPATH=. pytest tests/` passes with 100% success.
