# Spec: AppConfig Two-Way Serialization & Secure Persistence

- **Issue**: #30
- **State**: Approved
- **Date**: 2026-09-29
- **Branch**: `agent/issue-30-appconfig-two-way-serialization`
- **Reference**: `docs/superpowers/specs/2026-09-29-atbmind-ui-redesign-design.md` §3.4 & §4

---

## 1. Problem Statement

The configuration subsystem (`atbmind_core/config.py`) is currently **read-only**: it loads YAML from disk and applies environment variable overrides. There is no mechanism to persist updated configuration values back to disk.

The UI redesign spec (§3.4) requires a `SettingsDialog` that lets users change LLM parameters (Provider, Base URL, API Key, Model, Temperature) and "click save to auto-persist to `configs/config.yaml`". Without write-back support, any runtime configuration changes are lost on restart.

Additionally, API keys written to logs or stdout are a security risk. A sanitization helper is required to redact sensitive fields before any logging occurs.

---

## 2. Design Decisions (90% confidence autonomous decisions)

### 2.1 `save_app_config` Signature

```python
def save_app_config(
    config: AppConfig,
    path: Path = DEFAULT_CONFIG_PATH,
) -> None:
```

- **Atomic write via temp file + `os.replace`**: prevents partial writes corrupting the config.
- **Parent directory auto-creation**: `path.parent.mkdir(parents=True, exist_ok=True)`.
- **Env-var values are NOT written**: The `api_key` field is persisted as-is from the `AppConfig` object. If the value originated from an env var, the caller is responsible for deciding whether to persist it (i.e., the `SettingsDialog` passes the visible/edited value). This is the simplest correct model — no special env-var stripping logic needed at save time.
- **YAML structure**: Use `model.model_dump()` (Pydantic v2) to convert to plain dict, then `yaml.safe_dump` with `default_flow_style=False` and `allow_unicode=True`.

### 2.2 Sensitive Field Sanitization

```python
SENSITIVE_KEYS = frozenset({"api_key"})

def sanitize_config_for_logging(config: AppConfig) -> dict:
    """Returns a plain dict copy of the config with sensitive fields redacted."""
```

- Returns a `dict` (not an `AppConfig`) to avoid pydantic validation issues with redacted placeholder values.
- Redaction format: `"sk-***"` (preserves prefix format hint, truncates secret).
- Operates recursively on nested sub-models by dumping to dict first.

### 2.3 Global Config Update Helper

```python
def update_config(partial: dict, path: Path = DEFAULT_CONFIG_PATH) -> AppConfig:
    """Merge partial dict into current config, save, and return updated AppConfig."""
```

- Convenience function for the `SettingsDialog` use case.
- Loads current config from disk (bypassing env override for base), merges the partial dict, validates via `AppConfig(**merged)`, saves, and reloads the global singleton.

### 2.4 No Change to Environment Override Precedence

`load_config()` behavior is unchanged: environment variables always win over file values at runtime. `save_app_config` writes the object state to YAML; environment overrides are still applied at load time on top of what's on disk.

---

## 3. API Contract

### 3.1 `save_app_config`

```python
def save_app_config(config: AppConfig, path: Path = DEFAULT_CONFIG_PATH) -> None:
    """
    Writes an AppConfig object to a YAML file atomically.

    - Creates parent directories if they don't exist.
    - Uses a temporary file and os.replace for atomic write.
    - Does NOT redact sensitive fields — caller is responsible for deciding
      what to persist.

    Args:
        config: The AppConfig instance to persist.
        path: Destination YAML file path. Defaults to DEFAULT_CONFIG_PATH.

    Raises:
        OSError: If the file cannot be written (permissions, disk full, etc.)
    """
```

### 3.2 `sanitize_config_for_logging`

```python
def sanitize_config_for_logging(config: AppConfig) -> dict:
    """
    Returns a plain dict copy of config with sensitive fields redacted.

    Sensitive fields (e.g. api_key) are replaced with "***" regardless of value.
    Safe to pass to any logger or print statement.

    Args:
        config: The AppConfig instance to sanitize.

    Returns:
        dict: A serializable dict with sensitive values masked.
    """
```

### 3.3 `update_config`

```python
def update_config(partial: dict, path: Path = DEFAULT_CONFIG_PATH) -> AppConfig:
    """
    Merges a partial configuration dict into the persisted config, saves, and
    updates the global singleton.

    Args:
        partial: Dict of top-level or nested config keys to update.
                 Nested updates use dict merge (not deep merge — caller must
                 supply the full sub-dict for sub-models).
        path: Config file path. Defaults to DEFAULT_CONFIG_PATH.

    Returns:
        AppConfig: The newly saved and reloaded configuration.
    """
```

---

## 4. Test Cases Required

| Test | Description |
|------|-------------|
| `test_save_app_config_round_trip` | Save a modified `AppConfig` to a temp file, reload it, and assert all fields match. |
| `test_save_app_config_creates_parent_dirs` | Save to a nested path where parent dirs don't exist; verify they are created. |
| `test_save_app_config_llm_params` | Modify `provider`, `base_url`, `api_key`, `model` on `AppConfig.llm`, save, reload, verify each field. |
| `test_sanitize_config_for_logging_redacts_api_key` | Assert `api_key` is replaced with `"***"` in the returned dict. |
| `test_sanitize_config_for_logging_safe_fields_intact` | Assert non-sensitive fields (`app_name`, `llm.model`, etc.) remain unchanged. |
| `test_update_config_persists_and_reloads` | Call `update_config({"llm": {"model": "new-model"}})` against a temp file; verify the updated AppConfig is returned and the global singleton is updated. |
| `test_env_override_still_wins_after_save` | After saving a config to disk, set an env var for the same field; assert `load_config()` returns the env var value. |

---

## 5. Files to Modify / Create

| File | Change |
|------|--------|
| `atbmind_core/config.py` | Add `save_app_config`, `sanitize_config_for_logging`, `update_config`, `SENSITIVE_KEYS` |
| `tests/test_config.py` | Add new test functions (append to existing file, no existing tests modified) |
