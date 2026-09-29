# Plan: AppConfig Two-Way Serialization & Secure Persistence (Issue #30)

- **Spec**: `docs/superpowers/specs/issue-30-appconfig-two-way-serialization-spec.md`
- **Branch**: `agent/issue-30-appconfig-two-way-serialization`
- **Test command**: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_config.py -v`

---

## Task 1: Write failing tests for `save_app_config`

**File**: `tests/test_config.py` (append new tests)

Add these test functions:
1. `test_save_app_config_round_trip` — Save modified AppConfig, reload, assert equality.
2. `test_save_app_config_creates_parent_dirs` — Save to nested non-existent path, verify dirs created.
3. `test_save_app_config_llm_params` — Modify all LLM fields, save, reload, assert each field.

**Expected result before implementation**: `ImportError` or `AttributeError` on `save_app_config`.

**Run**:
```bash
PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_config.py::test_save_app_config_round_trip -v
```

---

## Task 2: Write failing tests for `sanitize_config_for_logging`

**File**: `tests/test_config.py` (append)

Add:
4. `test_sanitize_config_for_logging_redacts_api_key` — Assert `api_key` → `"***"`.
5. `test_sanitize_config_for_logging_safe_fields_intact` — Assert `app_name`, `llm.model` unchanged.

**Run**:
```bash
PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_config.py::test_sanitize_config_for_logging_redacts_api_key -v
```

---

## Task 3: Write failing tests for `update_config`

**File**: `tests/test_config.py` (append)

Add:
6. `test_update_config_persists_and_reloads` — Call `update_config`, verify returned config and file on disk.
7. `test_env_override_still_wins_after_save` — Save config, set env var, assert `load_config()` returns env value.

**Run**:
```bash
PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_config.py::test_update_config_persists_and_reloads -v
```

---

## Task 4: Implement `save_app_config`, `sanitize_config_for_logging`, `update_config`

**File**: `atbmind_core/config.py`

Add after existing `get_config` function:

```python
# ─────────────────────────────────────────────
# Sensitive field registry
# ─────────────────────────────────────────────
SENSITIVE_KEYS: frozenset[str] = frozenset({"api_key"})

def save_app_config(config: AppConfig, path: Path = DEFAULT_CONFIG_PATH) -> None:
    """Atomically writes AppConfig to YAML. Creates parent dirs as needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = config.model_dump()
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

def _redact_dict(data: dict, sensitive_keys: frozenset) -> dict:
    """Recursively redact sensitive keys in a dict."""
    result = {}
    for k, v in data.items():
        if k in sensitive_keys:
            result[k] = "***"
        elif isinstance(v, dict):
            result[k] = _redact_dict(v, sensitive_keys)
        else:
            result[k] = v
    return result

def sanitize_config_for_logging(config: AppConfig) -> dict:
    """Returns a plain dict copy of config with sensitive fields redacted."""
    raw = config.model_dump()
    return _redact_dict(raw, SENSITIVE_KEYS)

def update_config(partial: dict, path: Path = DEFAULT_CONFIG_PATH) -> AppConfig:
    """Merges partial dict into persisted config, saves, updates global singleton."""
    global _GLOBAL_CONFIG
    path = Path(path)
    # Load current raw data from disk (without env overrides for merge base)
    raw: dict[str, Any] = {}
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
            if isinstance(loaded, dict):
                raw = loaded
    # Merge: top-level keys are merged; sub-dict values replace (not deep-merged)
    for key, val in partial.items():
        if isinstance(val, dict) and isinstance(raw.get(key), dict):
            raw[key] = {**raw[key], **val}
        else:
            raw[key] = val
    # Validate via Pydantic
    new_config = AppConfig(**raw)
    save_app_config(new_config, path)
    # Apply env overrides and update singleton
    _GLOBAL_CONFIG = load_config(path)
    return _GLOBAL_CONFIG
```

Also add `import tempfile` to the imports.

**Run**:
```bash
PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_config.py -v
```

---

## Task 5: Run full existing test suite (regression check)

```bash
PYTHONPATH=src conda run -n ATBMind python -m pytest tests/ -v
```

All existing tests must continue to pass.

---

## Task 6: Commit

```bash
git add atbmind_core/config.py tests/test_config.py docs/superpowers/specs/issue-30-appconfig-two-way-serialization-spec.md docs/superpowers/plans/issue-30-appconfig-two-way-serialization-plan.md
git commit -m "feat(config): implement AppConfig two-way serialization & secure persistence (closes #30)"
```

---

## Task 7: Transition state to `reviewing`

```bash
python3 -c "
import yaml, os, tempfile, datetime
from pathlib import Path
path = Path('.github-agent-state.yml')
state = yaml.safe_load(path.read_text()) if path.exists() else {}
state['state'] = 'reviewing'
state['last_updated'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
tmp_fd, tmp_path = tempfile.mkstemp(dir='.', suffix='.tmp')
with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
    yaml.safe_dump(state, f, sort_keys=False)
os.replace(tmp_path, path)
print('State -> reviewing')
"
```
