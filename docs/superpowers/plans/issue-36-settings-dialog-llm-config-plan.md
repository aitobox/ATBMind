# Issue #36 Implementation Plan: SettingsDialog for LLM Configuration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the modal `SettingsDialog` in `apps/atbmind_desktop/widgets/settings_dialog.py` and comprehensive `pytest-qt` tests in `tests/test_settings_dialog.py`.

**Architecture:** Apple HIG styled modal QDialog featuring form fields for LLM provider, base URL, masked API key with reveal toggle, model name, and a synchronized QSlider for temperature (0.0 - 1.0). Provides a non-blocking `ConnectionTestWorker(QThread)` for validating LLM connectivity in the background, persists configuration atomically via `update_config`, and emits `config_updated(AppConfig)`.

**Tech Stack:** Python 3.12, PySide6 (QDialog, QSlider, QThread, Signals), pytest, pytest-qt (qtbot).

**Spec:** `docs/superpowers/specs/issue-36-settings-dialog-llm-config-spec.md`

## Global Constraints

- Never log or print the LLM API key in plaintext.
- Maintain full compatibility with PySide6 6.11+ and existing `AppConfig` models.
- All tests must pass with `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/`.

---

### Task 1: Complete SettingsDialog with Temperature Slider & Asynchronous ConnectionTestWorker

**Files:**
- Modify: `apps/atbmind_desktop/widgets/settings_dialog.py`
- Test: `tests/test_settings_dialog.py`

**Interfaces:**
- Consumes: `AppConfig`, `load_config`, `update_config` from `atbmind_core.config`, `OpenAICompatClient` from `atbmind_core.engine.llm_client`.
- Produces: `SettingsDialog(QDialog)`, `ConnectionTestWorker(QThread)`, signal `config_updated = Signal(object)`.

- [ ] **Step 1: Write initial failing test in tests/test_settings_dialog.py**
```python
import pytest
from PySide6.QtWidgets import QLineEdit, QSlider
from atbmind_core.config import AppConfig, LLMConfig
from apps.atbmind_desktop.widgets.settings_dialog import SettingsDialog

def test_settings_dialog_initialization(qtbot):
    cfg = AppConfig(llm=LLMConfig(provider="deepseek", base_url="https://api.deepseek.com", api_key="sk-secret123", model="deepseek-chat", temperature=0.7))
    dialog = SettingsDialog(config=cfg)
    qtbot.addWidget(dialog)

    assert dialog.provider_combo.currentText().lower() == "deepseek"
    assert dialog.base_url_edit.text() == "https://api.deepseek.com"
    assert dialog.api_key_edit.text() == "sk-secret123"
    assert dialog.api_key_edit.echoMode() == QLineEdit.EchoMode.Password
    assert dialog.model_edit.text() == "deepseek-chat"
    assert dialog.temp_slider.value() == 70
    assert "0.7" in dialog.temp_val_label.text()
```

- [ ] **Step 2: Run test to verify it fails**
Run: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_settings_dialog.py -v`
Expected: FAIL (AttributeError: 'SettingsDialog' object has no attribute 'temp_slider')

- [ ] **Step 3: Implement SettingsDialog and ConnectionTestWorker in apps/atbmind_desktop/widgets/settings_dialog.py**
Implement `ConnectionTestWorker(QThread)`:
- Signals: `test_passed = Signal(str)`, `test_failed = Signal(str)`
- Performs test completion with `OpenAICompatClient(base_url=..., api_key=..., model=..., timeout_seconds=5.0, max_retries=1)`
Implement `SettingsDialog`:
- Form fields with `QSlider` (0 to 100) mapped to 0.0 - 1.0 temperature, label `temp_val_label`.
- API Key mask toggle with `reveal_cb` (`QLineEdit.EchoMode.Password` vs `Normal`).
- `test_btn` connects to background `ConnectionTestWorker`.
- `save_btn` calls `update_config`, emits `config_updated(new_config)`, and calls `accept()`.

- [ ] **Step 4: Run test to verify it passes**
Run: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_settings_dialog.py -v`
Expected: PASS

- [ ] **Step 5: Commit changes**
`git add apps/atbmind_desktop/widgets/settings_dialog.py tests/test_settings_dialog.py`
`git commit -m "feat(ui): add temperature slider and ConnectionTestWorker to SettingsDialog (fixes #36)"`

---

### Task 2: Comprehensive Test Suite for SettingsDialog

**Files:**
- Modify: `tests/test_settings_dialog.py`

**Interfaces:**
- Consumes: `SettingsDialog`, `ConnectionTestWorker`, `AppConfig`
- Produces: Complete automated test suite covering reveal toggle, slider sync, save persistence, and mock connection testing.

- [ ] **Step 1: Add tests for reveal toggle, slider change, save action, and connection test**
Include:
- `test_reveal_password_toggle`
- `test_temperature_slider_updates_label`
- `test_save_persists_config_and_emits_signal`
- `test_connection_test_success_mocked`
- `test_connection_test_failure_mocked`
- `test_empty_base_url_validation`
- `test_api_key_not_leaked_in_logs`

- [ ] **Step 2: Run full test suite**
Run: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_settings_dialog.py -v`
Expected: ALL PASS

- [ ] **Step 3: Commit changes**
`git add tests/test_settings_dialog.py`
`git commit -m "test(ui): add comprehensive unit and qtbot tests for SettingsDialog"`
