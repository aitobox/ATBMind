"""
ATBMind Configuration Subsystem
Provides hierarchical configuration management with YAML persistence and environment variable overrides.
"""

from __future__ import annotations

import os
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
