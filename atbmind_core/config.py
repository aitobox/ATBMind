"""
ATBMind Configuration Subsystem
Provides hierarchical configuration management with YAML persistence and environment variable overrides.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, List, Optional
import yaml
from pydantic import BaseModel, Field

DEFAULT_CONFIG_PATH = Path("configs/config.yaml")

class ServerConfig(BaseModel):
    """HTTP/API server settings."""
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False

class LLMConfig(BaseModel):
    """LLM client connection and inference parameters."""
    provider: str = "openai"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o"
    temperature: float = 0.2
    timeout_seconds: float = 30.0
    max_retries: int = 3

class StorageConfig(BaseModel):
    """Local SQLite database settings."""
    db_path: str = "data/atbmind.db"
    in_memory: bool = False

class PluginConfig(BaseModel):
    """Plugin discovery and activation settings."""
    plugins_dir: str = "plugins"
    enabled_plugins: List[str] = Field(default_factory=lambda: ["draw"])

class AppConfig(BaseModel):
    """Root configuration for ATBMind."""
    app_name: str = "ATBMind"
    version: str = "0.1.0"
    env: str = "development"
    server: ServerConfig = Field(default_factory=ServerConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    plugins: PluginConfig = Field(default_factory=PluginConfig)

_GLOBAL_CONFIG: Optional[AppConfig] = None

def _apply_env_overrides(raw: dict[str, Any]) -> dict[str, Any]:
    """Applies ATBMIND_* environment variables onto configuration dictionary."""
    data = dict(raw)

    # Top-level overrides
    if "ATBMIND_APP_NAME" in os.environ:
        data["app_name"] = os.environ["ATBMIND_APP_NAME"]
    if "ATBMIND_VERSION" in os.environ:
        data["version"] = os.environ["ATBMIND_VERSION"]
    if "ATBMIND_ENV" in os.environ:
        data["env"] = os.environ["ATBMIND_ENV"]

    # Server overrides
    server = dict(data.get("server") or {})
    if "ATBMIND_HOST" in os.environ:
        server["host"] = os.environ["ATBMIND_HOST"]
    elif "ATBMIND_SERVER_HOST" in os.environ:
        server["host"] = os.environ["ATBMIND_SERVER_HOST"]

    if "ATBMIND_PORT" in os.environ:
        server["port"] = int(os.environ["ATBMIND_PORT"])
    elif "ATBMIND_SERVER_PORT" in os.environ:
        server["port"] = int(os.environ["ATBMIND_SERVER_PORT"])

    if "ATBMIND_DEBUG" in os.environ:
        server["debug"] = os.environ["ATBMIND_DEBUG"].strip().lower() in ("true", "1", "yes")
    elif "ATBMIND_SERVER_DEBUG" in os.environ:
        server["debug"] = os.environ["ATBMIND_SERVER_DEBUG"].strip().lower() in ("true", "1", "yes")
    data["server"] = server

    # LLM overrides
    llm = dict(data.get("llm") or {})
    if "ATBMIND_LLM_PROVIDER" in os.environ:
        llm["provider"] = os.environ["ATBMIND_LLM_PROVIDER"]
    if "ATBMIND_LLM_BASE_URL" in os.environ:
        llm["base_url"] = os.environ["ATBMIND_LLM_BASE_URL"]
    if "ATBMIND_LLM_API_KEY" in os.environ:
        llm["api_key"] = os.environ["ATBMIND_LLM_API_KEY"]
    if "ATBMIND_LLM_MODEL" in os.environ:
        llm["model"] = os.environ["ATBMIND_LLM_MODEL"]
    if "ATBMIND_LLM_TEMPERATURE" in os.environ:
        llm["temperature"] = float(os.environ["ATBMIND_LLM_TEMPERATURE"])
    if "ATBMIND_LLM_TIMEOUT" in os.environ:
        llm["timeout_seconds"] = float(os.environ["ATBMIND_LLM_TIMEOUT"])
    data["llm"] = llm

    # Storage overrides
    storage = dict(data.get("storage") or {})
    if "ATBMIND_STORAGE_DB_PATH" in os.environ:
        storage["db_path"] = os.environ["ATBMIND_STORAGE_DB_PATH"]
    elif "ATBMIND_DB_PATH" in os.environ:
        storage["db_path"] = os.environ["ATBMIND_DB_PATH"]

    if "ATBMIND_STORAGE_IN_MEMORY" in os.environ:
        storage["in_memory"] = os.environ["ATBMIND_STORAGE_IN_MEMORY"].strip().lower() in ("true", "1", "yes")
    data["storage"] = storage

    # Plugins overrides
    plugins = dict(data.get("plugins") or {})
    if "ATBMIND_PLUGINS_DIR" in os.environ:
        plugins["plugins_dir"] = os.environ["ATBMIND_PLUGINS_DIR"]
    data["plugins"] = plugins

    return data

def load_config(config_path: str | Path | None = None) -> AppConfig:
    """
    Loads configuration from a YAML file with environment variable overrides.

    Args:
        config_path: Path to config YAML. If None, checks ATBMIND_CONFIG_PATH or defaults to configs/config.yaml.

    Returns:
        AppConfig: Validated application configuration model.
    """
    if config_path is None:
        env_path = os.getenv("ATBMIND_CONFIG_PATH")
        target_path = Path(env_path) if env_path else DEFAULT_CONFIG_PATH
        is_default = env_path is None
    else:
        target_path = Path(config_path)
        is_default = False

    raw_data: dict[str, Any] = {}
    if target_path.exists():
        with open(target_path, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
            if isinstance(loaded, dict):
                raw_data = loaded
    elif not is_default:
        raise FileNotFoundError(f"Configuration file not found: {target_path}")

    merged = _apply_env_overrides(raw_data)
    return AppConfig(**merged)

def get_config(reload: bool = False, config_path: str | Path | None = None) -> AppConfig:
    """
    Provides a singleton instance of AppConfig.

    Args:
        reload: If True, forces re-reading configuration from disk and environment.
        config_path: Optional custom config file path.
    """
    global _GLOBAL_CONFIG
    if _GLOBAL_CONFIG is None or reload:
        _GLOBAL_CONFIG = load_config(config_path)
    return _GLOBAL_CONFIG


# ─────────────────────────────────────────────────────────────────────
# Two-way serialization & secure persistence (Issue #30)
# ─────────────────────────────────────────────────────────────────────

SENSITIVE_KEYS: frozenset[str] = frozenset({"api_key"})


def save_app_config(config: AppConfig, path: Path = DEFAULT_CONFIG_PATH) -> None:
    """
    Writes an AppConfig object to a YAML file atomically.

    Creates parent directories if they don't exist.
    Uses a temporary file and os.replace() for atomic write, preventing
    partial writes from corrupting the config file.

    Does NOT redact sensitive fields — the caller is responsible for deciding
    which values to persist (e.g., SettingsDialog passes the user-edited value).

    Args:
        config: The AppConfig instance to persist.
        path: Destination YAML file path. Defaults to DEFAULT_CONFIG_PATH.

    Raises:
        OSError: If the file cannot be written (permissions, disk full, etc.)
    """
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
    """Recursively redacts sensitive keys in a nested dict."""
    result: dict[str, Any] = {}
    for k, v in data.items():
        if k in sensitive_keys:
            result[k] = "***"
        elif isinstance(v, dict):
            result[k] = _redact_dict(v, sensitive_keys)
        else:
            result[k] = v
    return result


def sanitize_config_for_logging(config: AppConfig) -> dict:
    """
    Returns a plain dict copy of config with sensitive fields redacted.

    Sensitive fields (defined in SENSITIVE_KEYS, e.g. ``api_key``) are
    replaced with ``"***"`` regardless of their actual value.  The result is
    safe to pass to any logger or ``print`` statement without leaking secrets.
    The original ``config`` object is not mutated.

    Args:
        config: The AppConfig instance to sanitize.

    Returns:
        dict: A serializable dict with sensitive values masked.
    """
    raw = config.model_dump()
    return _redact_dict(raw, SENSITIVE_KEYS)


def update_config(partial: dict, path: Path = DEFAULT_CONFIG_PATH) -> AppConfig:
    """
    Merges a partial configuration dict into the persisted config, saves it
    atomically, and updates the global singleton.

    Nested sub-dict values are shallow-merged: the caller must supply the
    complete sub-dict for any sub-model they wish to update (e.g. the full
    ``llm`` section).  Top-level scalar keys are replaced directly.

    Args:
        partial: Dict of top-level or nested config keys to update.
        path: Config file path. Defaults to DEFAULT_CONFIG_PATH.

    Returns:
        AppConfig: The newly saved and reloaded configuration (with env
        overrides applied on top, as usual).
    """
    global _GLOBAL_CONFIG
    path = Path(path)
    # Load current raw data from disk (without env overrides — we want the
    # pure persisted baseline to merge against).
    raw: dict[str, Any] = {}
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
            if isinstance(loaded, dict):
                raw = loaded

    # Merge: shallow-merge sub-dicts, replace scalars.
    for key, val in partial.items():
        if isinstance(val, dict) and isinstance(raw.get(key), dict):
            raw[key] = {**raw[key], **val}
        else:
            raw[key] = val

    # Validate merged data via Pydantic before writing.
    new_config = AppConfig(**raw)
    save_app_config(new_config, path)

    # Reload with env overrides applied on top, update global singleton.
    _GLOBAL_CONFIG = load_config(path)
    return _GLOBAL_CONFIG
