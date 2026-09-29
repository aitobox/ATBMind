# Issue #36 Specification: Implement SettingsDialog for LLM Configuration

- **Issue**: #36 `[UI-Component] Implement SettingsDialog for LLM Configuration`
- **Branch**: `agent/issue-36-settings-dialog-llm-config`
- **Status**: Approved (Autonomous Decision >= 90% Confidence)
- **Date**: 2026-09-29

---

## 1. Objective

Refine and complete the modal settings dialog (`SettingsDialog`) in `apps/atbmind_desktop/widgets/settings_dialog.py` allowing users to view, test, and save global LLM API configuration with real-time hot-reloading and YAML persistence. Provide non-blocking background connection testing (`ConnectionTestWorker`), Apple HIG styled temperature slider (0.0 - 1.0) synchronized with value readout, password masking toggle, secure API key isolation (no plaintext secrets printed to logs/console), and comprehensive automated `pytest-qt` (`qtbot`) test coverage in `tests/test_settings_dialog.py`.

---

## 2. Scope & Technical Architecture

### 2.1 Component: `SettingsDialog(QDialog)`
Location: `apps/atbmind_desktop/widgets/settings_dialog.py`

#### A. Form Fields
1. **Provider (`QComboBox`)**:
   - Options: `OpenAI`, `DeepSeek`, `Ollama`, `Local` (case-insensitive mapping to `AppConfig.llm.provider`).
2. **Base URL (`QLineEdit`)**:
   - Text input with placeholder (e.g. `https://api.openai.com/v1`).
3. **API Key (`QLineEdit` + Reveal Toggle `QCheckBox`)**:
   - Masked via `QLineEdit.EchoMode.Password` by default.
   - Reveal toggle (`QCheckBox` or button "显示") switches echo mode to `Normal` when checked and back to `Password` when unchecked.
   - Security: API key is never written to loggers or standard output.
4. **Model Name (`QLineEdit`)**:
   - Text input with placeholder (e.g. `gpt-4o`).
5. **Temperature Slider (`QSlider` + `QLabel` / Value Sync)**:
   - Slider configured with range `0` to `100` (step `1` representing `0.00` to `1.00`), initialized from `config.llm.temperature`.
   - Value label dynamically updates to display `0.XX` format as the slider moves.

#### B. Asynchronous Connectivity Testing (`ConnectionTestWorker`)
- Background `QThread` executing connectivity verification using `OpenAICompatClient` with a lightweight probe and short timeout (e.g. 5.0 seconds).
- While testing:
  - Disables the `测试连接` button.
  - Updates `status_label` to `"正在测试连接..."` with neutral color.
- On completion:
  - Success signal `test_passed = Signal(str)` -> updates `status_label` with `"✓ 连接成功 (API 响应正常)"` in green (`#34c759`).
  - Failure signal `test_failed = Signal(str)` -> updates `status_label` with `"❌ 连接失败: <error>"` in red (`#ff3b30`).
  - Re-enables the `测试连接` button.
- Clean destruction on dialog close/cancel.

#### C. Persistence & Hot-Reloading
- **`保存 (Save)` Action**:
  - Gathers form field values.
  - Merges into `AppConfig` via `update_config` (persisting to `configs/config.yaml` atomically).
  - Updates in-memory `self.config`.
  - Emits `config_updated = Signal(object)` with the updated `AppConfig`.
  - Calls `self.accept()`.
- **`取消 (Cancel)` Action**:
  - Rejects without persisting changes (`self.reject()`).

---

## 3. Security & Logging Guardrails
- In adherence to Architectural Decision #10:
  - Never print or log `llm.api_key` in plaintext.
  - Any logging of configuration must use `sanitize_config_for_logging(config)` from `atbmind_core.config`.

---

## 4. Acceptance Criteria & Verification Plan

1. **Initial Values**: Dialog properly initializes all fields from the provided `AppConfig` (or loads global config if none provided).
2. **Password Masking Toggle**: Toggling the reveal checkbox toggles between `QLineEdit.EchoMode.Password` and `QLineEdit.EchoMode.Normal`.
3. **Temperature Slider**: Slider correctly sets and reflects temperature between 0.0 and 1.0.
4. **Connection Test**: Clicking `测试连接` starts background worker, properly emits success or failure, and updates UI status without blocking Qt event loop.
5. **Save & Persistence**: Clicking `保存` writes updated config to YAML file and emits `config_updated`.
6. **Automated Verification**:
   ```bash
   conda run -n ATBMind python -m pytest tests/test_settings_dialog.py
   ```
   All existing 100 tests continue to pass with 0 regressions:
   ```bash
   PYTHONPATH=src conda run -n ATBMind python -m pytest tests/
   ```
