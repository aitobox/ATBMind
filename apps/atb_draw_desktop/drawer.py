"""
ATBDraw Desktop Result Tuning Side Drawer (PySide6)
Displays active template pipeline cards with interactive parameter sliders for rapid Layer 3 re-dispatch.
"""

from __future__ import annotations

from typing import Any, Dict, List
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from atbmind_core.plugins.schemas import WorkflowStep


class ParameterSliderWidget(QWidget):
    """Interactive slider widget for a single numeric or boolean parameter slot."""

    valueChanged = Signal(str, object)

    def __init__(
        self,
        slot_name: str,
        initial_value: Any,
        slot_spec: Any = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.slot_name = slot_name
        self.current_value = initial_value
        self.is_float = isinstance(initial_value, float) or (
            isinstance(slot_spec, dict) and slot_spec.get("type") in ("float", "number")
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(2)

        header_layout = QHBoxLayout()
        self.label = QLabel(self.slot_name)
        self.label.setStyleSheet("font-weight: 500; font-size: 12px; color: #333;")
        self.val_label = QLabel(self._format_value(initial_value))
        self.val_label.setStyleSheet("font-size: 12px; color: #0066cc;")
        header_layout.addWidget(self.label)
        header_layout.addStretch()
        header_layout.addWidget(self.val_label)
        layout.addLayout(header_layout)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        slider_val = int(initial_value * 100) if self.is_float and isinstance(initial_value, (int, float)) else int(initial_value or 0)
        self.slider.setValue(max(0, min(100, slider_val)))
        self.slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self.slider)

    def _format_value(self, val: Any) -> str:
        if isinstance(val, float):
            return f"{val * 100:.1f}%"
        return str(val)

    def _on_slider_changed(self, value: int) -> None:
        if self.is_float:
            self.current_value = round(value / 100.0, 3)
            self.val_label.setText(f"{value}%")
        else:
            self.current_value = value
            self.val_label.setText(str(value))
        self.valueChanged.emit(self.slot_name, self.current_value)


class ResultTuningDrawer(QWidget):
    """
    Side drawer for fine-tuning executed template parameters.
    Allows users to adjust parameter sliders and click '微调重新生成' to re-dispatch Layer 3.
    """

    refine_requested = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._param_widgets: Dict[str, ParameterSliderWidget] = {}

        self.setFixedWidth(280)
        self.setStyleSheet(
            """
            ResultTuningDrawer {
                background-color: #f7f7f9;
                border-left: 1px solid #dcdce0;
            }
            """
        )

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 14, 12, 14)
        main_layout.setSpacing(10)

        title_label = QLabel("结果侧微调抽屉")
        title_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #1d1d1f;")
        main_layout.addWidget(title_label)

        desc_label = QLabel("已生效的智能精修模板与参数")
        desc_label.setStyleSheet("font-size: 11px; color: #86868b;")
        main_layout.addWidget(desc_label)

        # Scroll area for templates & sliders
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_container = QWidget()
        self.cards_layout = QVBoxLayout(self.scroll_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(12)
        self.scroll_area.setWidget(self.scroll_container)
        main_layout.addWidget(self.scroll_area)

        # Refine action button
        self.refine_btn = QPushButton("微调重新生成 ⚡")
        self.refine_btn.setFixedHeight(36)
        self.refine_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #0071e3;
                color: white;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #0077ed;
            }
            QPushButton:disabled {
                background-color: #c7c7cc;
            }
            """
        )
        self.refine_btn.setEnabled(False)
        self.refine_btn.clicked.connect(self._on_refine_clicked)
        main_layout.addWidget(self.refine_btn)

    def populate_steps(self, steps: List[WorkflowStep]) -> None:
        """Populates drawer cards with executed steps and parameter sliders."""
        self._clear_cards()
        self._param_widgets.clear()

        if not steps:
            empty_lbl = QLabel("暂无执行记录\n输入自然语言需求后生成")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_lbl.setStyleSheet("color: #8e8e93; font-size: 12px; margin-top: 40px;")
            self.cards_layout.addWidget(empty_lbl)
            self.refine_btn.setEnabled(False)
            return

        for step in steps:
            card = QFrame()
            card.setStyleSheet(
                """
                QFrame {
                    background-color: #ffffff;
                    border: 1px solid #e5e5ea;
                    border-radius: 8px;
                    padding: 8px;
                }
                """
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(8, 8, 8, 8)
            card_layout.setSpacing(6)

            step_name = QLabel(f"#{step.step} {step.name}")
            step_name.setStyleSheet("font-weight: 600; font-size: 13px; color: #1d1d1f;")
            card_layout.addWidget(step_name)

            tid_lbl = QLabel(f"ID: {step.template_id}")
            tid_lbl.setStyleSheet("font-size: 10px; color: #8e8e93;")
            card_layout.addWidget(tid_lbl)

            for slot_name, slot_val in step.slots.items():
                if isinstance(slot_val, (int, float)):
                    slider_widget = ParameterSliderWidget(slot_name, slot_val, parent=self)
                    self._param_widgets[slot_name] = slider_widget
                    card_layout.addWidget(slider_widget)
                else:
                    val_lbl = QLabel(f"{slot_name}: {slot_val}")
                    val_lbl.setStyleSheet("font-size: 11px; color: #555;")
                    card_layout.addWidget(val_lbl)

            self.cards_layout.addWidget(card)

        self.cards_layout.addStretch()
        self.refine_btn.setEnabled(True)

    def _clear_cards(self) -> None:
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def get_slot_overrides(self) -> Dict[str, Any]:
        """Returns currently adjusted parameter values from all drawer sliders."""
        return {name: w.current_value for name, w in self._param_widgets.items()}

    def _on_refine_clicked(self) -> None:
        overrides = self.get_slot_overrides()
        self.refine_requested.emit(overrides)
