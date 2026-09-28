import os
import tempfile
import pytest
from pydantic import ValidationError
from atbmind_core.config import (
    AppConfig,
    ServerConfig,
    LLMConfig,
    StorageConfig,
    PluginConfig,
    load_config,
    get_config,
)

def test_default_config_loading():
    """Verify that default configs/config.yaml loads properly."""
    cfg = load_config()
    assert isinstance(cfg, AppConfig)
    assert cfg.app_name == "ATBMind"
    assert cfg.version == "0.1.0"
    assert cfg.server.host == "127.0.0.1"
    assert cfg.server.port == 8000
    assert cfg.llm.provider == "openai"
    assert cfg.llm.model == "gpt-4o"
    assert "draw" in cfg.plugins.enabled_plugins

def test_custom_config_loading():
    """Verify loading from an arbitrary yaml file path."""
    yaml_content = """
app_name: "TestMind"
version: "0.9.9"
server:
  host: "0.0.0.0"
  port: 8888
  debug: false
llm:
  model: "claude-3-5-sonnet"
  temperature: 0.7
"""
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        temp_path = f.name

    try:
        cfg = load_config(temp_path)
        assert cfg.app_name == "TestMind"
        assert cfg.version == "0.9.9"
        assert cfg.server.host == "0.0.0.0"
        assert cfg.server.port == 8888
        assert cfg.server.debug is False
        assert cfg.llm.model == "claude-3-5-sonnet"
        assert cfg.llm.temperature == 0.7
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def test_env_override(monkeypatch):
    """Verify that ATBMIND_* environment variables take precedence."""
    monkeypatch.setenv("ATBMIND_APP_NAME", "EnvMind")
    monkeypatch.setenv("ATBMIND_PORT", "9999")
    monkeypatch.setenv("ATBMIND_DEBUG", "false")
    monkeypatch.setenv("ATBMIND_LLM_MODEL", "deepseek-chat")
    monkeypatch.setenv("ATBMIND_LLM_API_KEY", "sk-custom-key")
    monkeypatch.setenv("ATBMIND_STORAGE_DB_PATH", "/var/tmp/custom.db")

    cfg = load_config()
    assert cfg.app_name == "EnvMind"
    assert cfg.server.port == 9999
    assert cfg.server.debug is False
    assert cfg.llm.model == "deepseek-chat"
    assert cfg.llm.api_key == "sk-custom-key"
    assert cfg.storage.db_path == "/var/tmp/custom.db"

def test_invalid_config_validation():
    """Verify that type mismatches trigger Pydantic validation error."""
    yaml_content = """
server:
  port: "invalid_not_a_number"
"""
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        temp_path = f.name

    try:
        with pytest.raises(ValidationError):
            load_config(temp_path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def test_get_config_singleton():
    """Verify singleton caching and reload behavior."""
    cfg1 = get_config(reload=True)
    cfg2 = get_config(reload=False)
    assert cfg1 is cfg2

    cfg3 = get_config(reload=True)
    assert cfg3 is not cfg1
    assert cfg3 == cfg1
