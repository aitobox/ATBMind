import os
import tempfile
from pathlib import Path
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
    save_app_config,
    sanitize_config_for_logging,
    update_config,
    SENSITIVE_KEYS,
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

# ─────────────────────────────────────────────────────────────────────
# Tests for save_app_config (Issue #30)
# ─────────────────────────────────────────────────────────────────────

def test_save_app_config_round_trip():
    """Save a modified AppConfig to a temp file, reload it, assert all fields match."""
    original = AppConfig(
        app_name="RoundTripMind",
        version="9.9.9",
        env="production",
        server=ServerConfig(host="0.0.0.0", port=7777, debug=True),
        llm=LLMConfig(provider="anthropic", base_url="https://api.anthropic.com/v1",
                      api_key="sk-test-round-trip", model="claude-opus-4",
                      temperature=0.5, timeout_seconds=60.0, max_retries=5),
        storage=StorageConfig(db_path="/tmp/round_trip.db", in_memory=False),
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "config.yaml"
        save_app_config(original, target)
        assert target.exists(), "Config file should have been created"

        reloaded = load_config(target)

    assert reloaded.app_name == "RoundTripMind"
    assert reloaded.version == "9.9.9"
    assert reloaded.env == "production"
    assert reloaded.server.host == "0.0.0.0"
    assert reloaded.server.port == 7777
    assert reloaded.server.debug is True
    assert reloaded.llm.provider == "anthropic"
    assert reloaded.llm.base_url == "https://api.anthropic.com/v1"
    assert reloaded.llm.api_key == "sk-test-round-trip"
    assert reloaded.llm.model == "claude-opus-4"
    assert reloaded.llm.temperature == 0.5
    assert reloaded.llm.timeout_seconds == 60.0
    assert reloaded.llm.max_retries == 5
    assert reloaded.storage.db_path == "/tmp/round_trip.db"


def test_save_app_config_creates_parent_dirs():
    """Save to a nested path where parent dirs don't exist; verify they are created."""
    with tempfile.TemporaryDirectory() as tmpdir:
        nested = Path(tmpdir) / "a" / "b" / "c" / "config.yaml"
        assert not nested.parent.exists()

        cfg = AppConfig()
        save_app_config(cfg, nested)

        assert nested.parent.exists(), "Parent directories should have been created"
        assert nested.exists(), "Config file should exist at nested path"
        reloaded = load_config(nested)
        assert reloaded.app_name == "ATBMind"


def test_save_app_config_llm_params():
    """Modify all LLM parameters, save, reload, verify each field persists correctly."""
    cfg = AppConfig()
    cfg.llm.provider = "deepseek"
    cfg.llm.base_url = "https://api.deepseek.com/v1"
    cfg.llm.api_key = "sk-deepseek-secret"
    cfg.llm.model = "deepseek-chat"
    cfg.llm.temperature = 0.9
    cfg.llm.timeout_seconds = 120.0
    cfg.llm.max_retries = 1

    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "config.yaml"
        save_app_config(cfg, target)
        reloaded = load_config(target)

    assert reloaded.llm.provider == "deepseek"
    assert reloaded.llm.base_url == "https://api.deepseek.com/v1"
    assert reloaded.llm.api_key == "sk-deepseek-secret"
    assert reloaded.llm.model == "deepseek-chat"
    assert reloaded.llm.temperature == 0.9
    assert reloaded.llm.timeout_seconds == 120.0
    assert reloaded.llm.max_retries == 1


# ─────────────────────────────────────────────────────────────────────
# Tests for sanitize_config_for_logging (Issue #30)
# ─────────────────────────────────────────────────────────────────────

def test_sanitize_config_for_logging_redacts_api_key():
    """Assert api_key is replaced with '***' in the sanitized dict."""
    cfg = AppConfig()
    cfg.llm.api_key = "sk-supersecret-key-12345"

    sanitized = sanitize_config_for_logging(cfg)

    assert isinstance(sanitized, dict), "sanitize_config_for_logging must return a dict"
    assert sanitized["llm"]["api_key"] == "***", "api_key must be redacted"
    # Ensure the original config is not mutated
    assert cfg.llm.api_key == "sk-supersecret-key-12345"


def test_sanitize_config_for_logging_safe_fields_intact():
    """Assert non-sensitive fields are unchanged in the sanitized dict."""
    cfg = AppConfig(
        app_name="SafeCheck",
        version="1.2.3",
    )
    cfg.llm.model = "gpt-4o-mini"
    cfg.llm.provider = "openai"
    cfg.llm.api_key = "sk-hidden"

    sanitized = sanitize_config_for_logging(cfg)

    assert sanitized["app_name"] == "SafeCheck"
    assert sanitized["version"] == "1.2.3"
    assert sanitized["llm"]["model"] == "gpt-4o-mini"
    assert sanitized["llm"]["provider"] == "openai"
    assert sanitized["llm"]["api_key"] == "***"


def test_sensitive_keys_constant():
    """Assert SENSITIVE_KEYS contains 'api_key'."""
    assert "api_key" in SENSITIVE_KEYS


# ─────────────────────────────────────────────────────────────────────
# Tests for update_config (Issue #30)
# ─────────────────────────────────────────────────────────────────────

def test_update_config_persists_and_reloads():
    """Call update_config, verify returned config and file on disk reflect changes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "config.yaml"
        # Write an initial config
        initial = AppConfig(app_name="InitialMind")
        save_app_config(initial, target)

        # Update llm model via update_config
        returned = update_config({"llm": {"model": "new-model-v2"}}, path=target)

        assert returned.llm.model == "new-model-v2", "Returned config should have new model"
        # Verify the file on disk was updated
        from_disk = load_config(target)
        assert from_disk.llm.model == "new-model-v2", "Disk file should have new model"
        # Other fields preserved
        assert from_disk.app_name == "InitialMind"


def test_update_config_updates_global_singleton(monkeypatch):
    """update_config should update the global _GLOBAL_CONFIG singleton."""
    import atbmind_core.config as config_module

    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "config.yaml"
        initial = AppConfig(app_name="SingletonTest")
        save_app_config(initial, target)

        # Force global singleton to current state
        monkeypatch.setattr(config_module, "_GLOBAL_CONFIG", None)

        result = update_config({"app_name": "UpdatedSingleton"}, path=target)
        assert result.app_name == "UpdatedSingleton"
        # The singleton should now be set
        assert config_module._GLOBAL_CONFIG is not None


def test_env_override_still_wins_after_save(monkeypatch):
    """After saving a config with one model, an env var for the same field should win on load."""
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "config.yaml"
        cfg = AppConfig()
        cfg.llm.model = "disk-model"
        save_app_config(cfg, target)

        monkeypatch.setenv("ATBMIND_LLM_MODEL", "env-model-wins")
        reloaded = load_config(target)

        assert reloaded.llm.model == "env-model-wins", "Env var must override disk value"
