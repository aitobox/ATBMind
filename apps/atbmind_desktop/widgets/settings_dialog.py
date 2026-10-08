"""
ATBMind SettingsDialog
Modal settings dialog allowing users to view, test, and save global LLM API configuration with YAML persistence.
Adheres to Apple HIG Preferences and macOS System Settings design patterns.
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
    QFrame,
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
from apps.atbmind_desktop.theme import (
    MODERN_COMBOBOX_QSS,
    BrandAssets,
    ThemeColors,
    ThemeFonts,
    ThemeRadii,
)

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
        timeout_seconds: float = 3.0,
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
        self.setMinimumSize(540, 440)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {ThemeColors.BG_WINDOW};
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QLabel {{
                font-size: 13px;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QFrame#settingsCard {{
                background-color: #FFFFFF;
                border: 1px solid {ThemeColors.BORDER_CARD};
                border-radius: {ThemeRadii.CARD};
            }}
            QLineEdit {{
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-radius: {ThemeRadii.BUTTON};
                padding: 6px 10px;
                font-size: 13px;
                background-color: {ThemeColors.BG_INPUT};
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QLineEdit:focus {{
                border: 1.5px solid {ThemeColors.BORDER_FOCUS};
                background-color: #FFFFFF;
            }}
            {MODERN_COMBOBOX_QSS}
            QSlider::groove:horizontal {{
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                height: 4px;
                background: {ThemeColors.BORDER_SUBTLE};
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background: {ThemeColors.PRIMARY};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: #FFFFFF;
                border: 1px solid {ThemeColors.BORDER_STRONG};
                width: 18px;
                margin-top: -7px;
                margin-bottom: -7px;
                border-radius: 9px;
            }}
            QSlider::handle:horizontal:hover {{
                border: 1px solid {ThemeColors.PRIMARY};
            }}
            QPushButton {{
                border: 1px solid {ThemeColors.BORDER_STRONG};
                border-radius: {ThemeRadii.BUTTON};
                padding: 6px 16px;
                font-size: 13px;
                font-weight: 500;
                background-color: #FFFFFF;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.BG_INPUT};
                border-color: {ThemeColors.PRIMARY};
            }}
            QPushButton:disabled {{
                color: {ThemeColors.TEXT_MUTED};
                background-color: {ThemeColors.BG_INPUT};
                border-color: {ThemeColors.BORDER_SUBTLE};
            }}
            QPushButton#primaryBtn {{
                background-color: {ThemeColors.PRIMARY};
                color: #FFFFFF;
                border: 1px solid {ThemeColors.PRIMARY};
                font-weight: 600;
            }}
            QPushButton#primaryBtn:hover {{
                background-color: {ThemeColors.PRIMARY_HOVER};
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        # Header title
        title_label = QLabel("⚙️ 全局模型与服务偏好")
        title_label.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {ThemeColors.TEXT_PRIMARY};")
        main_layout.addWidget(title_label)

        # Settings Card Container
        card = QFrame()
        card.setObjectName("settingsCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(14)

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
        self.reveal_cb.setCursor(Qt.CursorShape.PointingHandCursor)
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
        self.temp_val_label.setFixedWidth(46)
        self.temp_val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.temp_val_label.setStyleSheet(f"""
            font-family: {ThemeFonts.FONT_MONO};
            font-size: 12px;
            color: {ThemeColors.PRIMARY};
            background-color: {ThemeColors.PRIMARY_LIGHT};
            border-radius: 4px;
            padding: 2px 4px;
        """)

        self.temp_slider.valueChanged.connect(self._on_slider_changed)
        temp_layout.addWidget(self.temp_slider, 1)
        temp_layout.addWidget(self.temp_val_label)
        form_layout.addRow("温度 (Temperature):", temp_layout)

        card_layout.addLayout(form_layout)
        main_layout.addWidget(card)

        # Status / Feedback label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"font-size: 12px; color: {ThemeColors.TEXT_MUTED}; min-height: 18px;")
        main_layout.addWidget(self.status_label)

        # Mascot Brand Identity Card
        self.mascot_card = QFrame()
        self.mascot_card.setObjectName("mascotCard")
        self.mascot_card.setStyleSheet(f"""
            QFrame#mascotCard {{
                background-color: #FFFFFF;
                border: 1px solid {ThemeColors.BORDER_CARD};
                border-radius: {ThemeRadii.CARD};
            }}
        """)
        mascot_layout = QHBoxLayout(self.mascot_card)
        mascot_layout.setContentsMargins(12, 8, 12, 8)
        mascot_layout.setSpacing(12)

        self.mascot_avatar_label = QLabel(self.mascot_card)
        self.mascot_avatar_label.setFixedSize(48, 48)
        self.mascot_avatar_label.setScaledContents(True)
        self.mascot_avatar_label.setPixmap(BrandAssets.get_mascot_avatar(48))
        mascot_layout.addWidget(self.mascot_avatar_label)

        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)

        app_title = QLabel("ATBMind Desktop  v0.1.0", self.mascot_card)
        app_title.setStyleSheet(f"""
            QLabel {{
                font-size: 13px;
                font-weight: 700;
                color: {ThemeColors.TEXT_PRIMARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        info_layout.addWidget(app_title)

        app_slogan = QLabel("Your Loyal & Clever AI Desktop Companion 🐾", self.mascot_card)
        app_slogan.setStyleSheet(f"""
            QLabel {{
                font-size: 11px;
                color: {ThemeColors.TEXT_SECONDARY};
                font-family: {ThemeFonts.FONT_STACK};
            }}
        """)
        info_layout.addWidget(app_slogan)

        mascot_layout.addLayout(info_layout)
        mascot_layout.addStretch(1)

        main_layout.addWidget(self.mascot_card)

        # Buttons
        btn_layout = QHBoxLayout()
        self.test_btn = QPushButton("测试连接")
        self.test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.test_btn.clicked.connect(self._on_test_connection)
        btn_layout.addWidget(self.test_btn)

        btn_layout.addStretch(1)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("保存配置")
        self.save_btn.setObjectName("primaryBtn")
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
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
            self.status_label.setStyleSheet(f"font-size: 12px; color: {ThemeColors.ERROR};")
            return

        self.test_btn.setEnabled(False)
        self.status_label.setText("✓ 格式验证通过 (服务配置有效，正在测试连接...)")
        self.status_label.setStyleSheet(f"font-size: 12px; color: {ThemeColors.PRIMARY};")

        api_key = self.api_key_edit.text().strip()
        model = self.model_edit.text().strip() or "gpt-4o"

        self._test_worker = ConnectionTestWorker(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout_seconds=3.0,
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
        self.status_label.setStyleSheet(f"font-size: 12px; color: {ThemeColors.SUCCESS};")

    def _on_test_failed(self, message: str) -> None:
        self.test_btn.setEnabled(True)
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"font-size: 12px; color: {ThemeColors.ERROR};")

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
            self._test_worker.quit()
            self._test_worker.wait(100)

    def closeEvent(self, event) -> None:
        self.stop_worker()
        super().closeEvent(event)
