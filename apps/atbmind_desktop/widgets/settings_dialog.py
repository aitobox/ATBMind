"""
ATBMind SettingsDialog
Modal settings dialog allowing users to view, test, and save global LLM API configuration with YAML persistence.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from atbmind_core.config import AppConfig, load_config, update_config
from atbmind_core.engine.llm_client import OpenAICompatClient

logger = logging.getLogger("atbmind.desktop.settings_dialog")

_ACTIVE_TEST_WORKERS: list[ConnectionTestWorker] = []


class ConnectionTestWorker(QThread):
    """
    Background worker that performs a non-blocking connectivity probe
    against the configured OpenAI-compatible LLM endpoint.
    """

    test_passed = Signal(str)
    test_failed = Signal(str)

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 5.0,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def run(self) -> None:
        try:
            client = OpenAICompatClient(
                base_url=self.base_url,
                api_key=self.api_key,
                model=self.model or "gpt-4o",
                timeout_seconds=self.timeout_seconds,
                max_retries=1,
            )
            # Perform a lightweight ping completion probe
            client.chat_completion(
                messages=[{"role": "user", "content": "ping"}],
                temperature=0.0,
            )
            self.test_passed.emit("✓ 连接成功 (API 响应正常)")
        except Exception as e:
            logger.debug("LLM connectivity check failed: %s", type(e).__name__)
            self.test_failed.emit(f"❌ 连接失败: {e}")


class SettingsDialog(QDialog):
    """
    Apple HIG styled modal configuration dialog for global LLM and engine settings.
    """

    config_updated = Signal(object)  # Emits new AppConfig

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        config: Optional[AppConfig] = None,
        config_path: Optional[Path | str] = None,
    ) -> None:
        super().__init__(parent)
        self.config_path = Path(config_path) if config_path else None
        self.config = config or load_config(self.config_path)
        self._test_worker: Optional[ConnectionTestWorker] = None
        self.destroyed.connect(lambda *args: self.stop_worker())
        self._init_ui()
        self._load_values()

    def _init_ui(self) -> None:
        self.setWindowTitle("⚙️ 设置 (Settings)")
        self.setMinimumSize(500, 390)
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }
            QLabel {
                font-size: 13px;
                color: #1d1d1f;
            }
            QLineEdit, QComboBox {
                border: 1px solid #d2d2d7;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
                background-color: #f5f5f7;
                color: #1d1d1f;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #0071e3;
                background-color: #ffffff;
            }
            QSlider::groove:horizontal {
                border: 1px solid #d2d2d7;
                height: 4px;
                background: #e5e5ea;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #0071e3;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: 1px solid #c7c7cc;
                width: 18px;
                margin-top: -7px;
                margin-bottom: -7px;
                border-radius: 9px;
            }
            QSlider::handle:horizontal:hover {
                border: 1px solid #0071e3;
            }
            QPushButton {
                border: 1px solid #d2d2d7;
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 13px;
                background-color: #f5f5f7;
                color: #1d1d1f;
            }
            QPushButton:hover {
                background-color: #e8e8ed;
            }
            QPushButton:disabled {
                color: #8e8e93;
                background-color: #f5f5f7;
                border-color: #e5e5ea;
            }
            QPushButton#primaryBtn {
                background-color: #0071e3;
                color: #ffffff;
                border: none;
                font-weight: 600;
            }
            QPushButton#primaryBtn:hover {
                background-color: #0077ed;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # Header title
        title_label = QLabel("全局模型与推理配置")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #1d1d1f;")
        main_layout.addWidget(title_label)

        # Form Layout
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form_layout.setSpacing(12)

        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["OpenAI", "DeepSeek", "Ollama", "Local"])
        form_layout.addRow("服务提供商:", self.provider_combo)

        self.base_url_edit = QLineEdit()
        self.base_url_edit.setPlaceholderText("https://api.openai.com/v1")
        form_layout.addRow("Base URL:", self.base_url_edit)

        # API Key layout with mask toggle
        key_layout = QHBoxLayout()
        key_layout.setSpacing(8)
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("sk-...")
        key_layout.addWidget(self.api_key_edit, 1)

        self.reveal_cb = QCheckBox("显示")
        self.reveal_cb.toggled.connect(self._toggle_reveal_key)
        key_layout.addWidget(self.reveal_cb)
        form_layout.addRow("API Key:", key_layout)

        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("gpt-4o")
        form_layout.addRow("模型名称:", self.model_edit)

        # Temperature slider layout with live value readout
        temp_layout = QHBoxLayout()
        temp_layout.setSpacing(10)
        self.temp_slider = QSlider(Qt.Orientation.Horizontal)
        self.temp_slider.setRange(0, 100)
        self.temp_slider.setSingleStep(5)
        self.temp_slider.setValue(20)

        self.temp_val_label = QLabel("0.20")
        self.temp_val_label.setFixedWidth(40)
        self.temp_val_label.setStyleSheet("font-family: monospace; font-size: 13px; color: #1d1d1f;")

        self.temp_slider.valueChanged.connect(self._on_slider_changed)
        temp_layout.addWidget(self.temp_slider, 1)
        temp_layout.addWidget(self.temp_val_label)
        form_layout.addRow("温度 (Temperature):", temp_layout)

        main_layout.addLayout(form_layout)

        # Status / Feedback label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("font-size: 12px; color: #86868b;")
        main_layout.addWidget(self.status_label)

        # Buttons
        btn_layout = QHBoxLayout()
        self.test_btn = QPushButton("测试连接")
        self.test_btn.clicked.connect(self._on_test_connection)
        btn_layout.addWidget(self.test_btn)

        btn_layout.addStretch(1)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("保存")
        self.save_btn.setObjectName("primaryBtn")
        self.save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(self.save_btn)

        main_layout.addLayout(btn_layout)

    def _load_values(self) -> None:
        llm = self.config.llm
        provider_target = llm.provider.lower()
        for idx in range(self.provider_combo.count()):
            if self.provider_combo.itemText(idx).lower() == provider_target:
                self.provider_combo.setCurrentIndex(idx)
                break

        self.base_url_edit.setText(llm.base_url)
        self.api_key_edit.setText(llm.api_key)
        self.model_edit.setText(llm.model)
        slider_val = int(round(max(0.0, min(1.0, llm.temperature)) * 100))
        self.temp_slider.setValue(slider_val)
        self.temp_val_label.setText(f"{slider_val / 100.0:.2f}")

    def _on_slider_changed(self, value: int) -> None:
        self.temp_val_label.setText(f"{value / 100.0:.2f}")

    def _toggle_reveal_key(self, checked: bool) -> None:
        if checked:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)

    def _on_test_connection(self) -> None:
        """Asynchronously tests connectivity via LLMClient in background."""
        base_url = self.base_url_edit.text().strip()
        if not base_url:
            self.status_label.setText("❌ Base URL 不能为空")
            self.status_label.setStyleSheet("font-size: 12px; color: #ff3b30;")
            return

        self.test_btn.setEnabled(False)
        self.status_label.setText("✓ 格式验证通过 (服务配置有效，正在测试连接...)")
        self.status_label.setStyleSheet("font-size: 12px; color: #0071e3;")

        api_key = self.api_key_edit.text().strip()
        model = self.model_edit.text().strip() or "gpt-4o"

        self._test_worker = ConnectionTestWorker(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout_seconds=5.0,
            parent=None,
        )
        worker = self._test_worker
        _ACTIVE_TEST_WORKERS.append(worker)

        def _on_worker_finished():
            if worker in _ACTIVE_TEST_WORKERS:
                _ACTIVE_TEST_WORKERS.remove(worker)

        worker.finished.connect(_on_worker_finished)
        worker.test_passed.connect(self._on_test_passed)
        worker.test_failed.connect(self._on_test_failed)
        worker.start()

    def _on_test_passed(self, message: str) -> None:
        self.test_btn.setEnabled(True)
        self.status_label.setText("✓ 连接成功 (服务配置有效，API 响应正常)")
        self.status_label.setStyleSheet("font-size: 12px; color: #34c759;")

    def _on_test_failed(self, message: str) -> None:
        self.test_btn.setEnabled(True)
        self.status_label.setText(message)
        self.status_label.setStyleSheet("font-size: 12px; color: #ff3b30;")

    def _on_save(self) -> None:
        try:
            temperature = round(self.temp_slider.value() / 100.0, 2)
            partial_llm = {
                "llm": {
                    "provider": self.provider_combo.currentText().lower(),
                    "base_url": self.base_url_edit.text().strip(),
                    "api_key": self.api_key_edit.text().strip(),
                    "model": self.model_edit.text().strip() or "gpt-4o",
                    "temperature": float(temperature),
                    "timeout_seconds": self.config.llm.timeout_seconds,
                    "max_retries": self.config.llm.max_retries,
                }
            }
            new_config = update_config(partial_llm, path=self.config_path)
            self.config = new_config
            self.config_updated.emit(new_config)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"无法保存配置: {e}")

    def stop_worker(self) -> None:
        if self._test_worker and self._test_worker.isRunning():
            self._test_worker.terminate()
            self._test_worker.wait(1000)

    def reject(self) -> None:
        self.stop_worker()
        super().reject()

    def accept(self) -> None:
        self.stop_worker()
        super().accept()

    def closeEvent(self, event) -> None:
        self.stop_worker()
        super().closeEvent(event)


def _cleanup_all_workers():
    for w in list(_ACTIVE_TEST_WORKERS):
        if w.isRunning():
            w.terminate()
            w.wait(500)


import atexit
atexit.register(_cleanup_all_workers)
