"""
Unit and integration tests for SettingsDialog and ConnectionTestWorker.
"""

from pathlib import Path
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLineEdit, QSlider

from atbmind_core.config import AppConfig, LLMConfig, save_app_config, sanitize_config_for_logging
from atbmind_core.engine.llm_client import OpenAICompatClient
from apps.atbmind_desktop.widgets.settings_dialog import ConnectionTestWorker, SettingsDialog


def test_settings_dialog_initialization(qtbot):
    cfg = AppConfig(
        llm=LLMConfig(
            provider="deepseek",
            base_url="https://api.deepseek.com",
            api_key="sk-secret123",
            model="deepseek-chat",
            temperature=0.7,
        )
    )
    dialog = SettingsDialog(config=cfg)
    qtbot.addWidget(dialog)

    assert dialog.provider_combo.currentText().lower() == "deepseek"
    assert dialog.base_url_edit.text() == "https://api.deepseek.com"
    assert dialog.api_key_edit.text() == "sk-secret123"
    assert dialog.api_key_edit.echoMode() == QLineEdit.EchoMode.Password
    assert dialog.model_edit.text() == "deepseek-chat"
    assert hasattr(dialog, "temp_slider")
    assert isinstance(dialog.temp_slider, QSlider)
    assert dialog.temp_slider.value() == 70
    assert "0.7" in dialog.temp_val_label.text()


def test_reveal_password_toggle(qtbot):
    cfg = AppConfig(llm=LLMConfig(api_key="sk-secret-password-xyz"))
    dialog = SettingsDialog(config=cfg)
    qtbot.addWidget(dialog)

    assert dialog.api_key_edit.echoMode() == QLineEdit.EchoMode.Password

    # Toggle reveal on
    dialog.reveal_cb.setChecked(True)
    assert dialog.api_key_edit.echoMode() == QLineEdit.EchoMode.Normal

    # Toggle reveal off
    dialog.reveal_cb.setChecked(False)
    assert dialog.api_key_edit.echoMode() == QLineEdit.EchoMode.Password


def test_temperature_slider_updates_label(qtbot):
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)

    dialog.temp_slider.setValue(85)
    assert dialog.temp_val_label.text() == "0.85"

    dialog.temp_slider.setValue(0)
    assert dialog.temp_val_label.text() == "0.00"

    dialog.temp_slider.setValue(100)
    assert dialog.temp_val_label.text() == "1.00"


def test_empty_base_url_validation(qtbot):
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)

    dialog.base_url_edit.setText("   ")
    dialog._on_test_connection()

    assert "Base URL 不能为空" in dialog.status_label.text()
    assert dialog.test_btn.isEnabled()


def test_connection_test_success_mocked(qtbot, monkeypatch):
    monkeypatch.setattr(
        OpenAICompatClient,
        "chat_completion",
        lambda self, messages, **kwargs: "pong",
    )

    dialog = SettingsDialog()
    qtbot.addWidget(dialog)
    dialog.base_url_edit.setText("https://api.mock.test/v1")
    dialog.api_key_edit.setText("sk-testkey")

    dialog._on_test_connection()
    qtbot.waitUntil(lambda: "连接成功" in dialog.status_label.text(), timeout=2000)
    assert dialog.test_btn.isEnabled()


def test_connection_test_failure_mocked(qtbot, monkeypatch):
    def _mock_fail(self, messages, **kwargs):
        raise RuntimeError("Connection refused by endpoint")

    monkeypatch.setattr(OpenAICompatClient, "chat_completion", _mock_fail)

    dialog = SettingsDialog()
    qtbot.addWidget(dialog)
    dialog.base_url_edit.setText("https://api.mock.test/v1")

    dialog._on_test_connection()
    qtbot.waitUntil(lambda: "连接失败" in dialog.status_label.text(), timeout=2000)
    assert "Connection refused" in dialog.status_label.text()
    assert dialog.test_btn.isEnabled()


def test_save_persists_config_and_emits_signal(qtbot, tmp_path, monkeypatch):
    custom_cfg_path = tmp_path / "config.yaml"
    initial_cfg = AppConfig()
    save_app_config(initial_cfg, path=custom_cfg_path)
    monkeypatch.setenv("ATBMIND_CONFIG_PATH", str(custom_cfg_path))

    dialog = SettingsDialog(config=initial_cfg, config_path=custom_cfg_path)
    qtbot.addWidget(dialog)

    # Set new form values
    provider_idx = dialog.provider_combo.findText("Ollama", Qt.MatchFlag.MatchFixedString)
    if provider_idx >= 0:
        dialog.provider_combo.setCurrentIndex(provider_idx)
    dialog.base_url_edit.setText("http://localhost:11434/v1")
    dialog.api_key_edit.setText("ollama-key")
    dialog.model_edit.setText("llama3.1")
    dialog.temp_slider.setValue(45)

    emitted_configs = []
    dialog.config_updated.connect(lambda cfg: emitted_configs.append(cfg))

    dialog._on_save()

    assert len(emitted_configs) == 1
    new_cfg = emitted_configs[0]
    assert new_cfg.llm.provider == "ollama"
    assert new_cfg.llm.base_url == "http://localhost:11434/v1"
    assert new_cfg.llm.api_key == "ollama-key"
    assert new_cfg.llm.model == "llama3.1"
    assert new_cfg.llm.temperature == 0.45


def test_api_key_security_isolation(qtbot):
    secret_key = "sk-super-secret-production-key-xyz"
    cfg = AppConfig(llm=LLMConfig(api_key=secret_key))
    dialog = SettingsDialog(config=cfg)
    qtbot.addWidget(dialog)

    # Ensure sanitization does not expose the key
    sanitized = sanitize_config_for_logging(dialog.config)
    assert sanitized["llm"]["api_key"] == "***"
    assert secret_key not in repr(sanitized)


def test_settings_dialog_contains_mascot_card(qtbot):
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    assert hasattr(dialog, "mascot_card")
    assert dialog.mascot_card.isVisible()

