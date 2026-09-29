"""
Unit and integration tests for SettingsDialog and ConnectionTestWorker.
"""

import pytest
from PySide6.QtWidgets import QLineEdit, QSlider
from atbmind_core.config import AppConfig, LLMConfig
from apps.atbmind_desktop.widgets.settings_dialog import SettingsDialog


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
