"""
ATBDraw Official Desktop Client Application (PySide6)
Implements drag-and-drop image uploading, natural language 'Mind-Eye' generation,
and side-drawer result parameter micro-tuning.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from atbmind_core.engine.completer import LatentIntentCompleter
from atbmind_core.engine.dispatcher import SlotDispatcher
from atbmind_core.engine.planner import WorkflowPlanner
from atbmind_core.plugins.schemas import StructuredIntentDraft, WorkflowExecutionReport, WorkflowPlan
from apps.atb_draw_desktop.drawer import ResultTuningDrawer
from plugins.draw.plugin import DrawPlugin


class ImagePreviewCard(QFrame):
    """Card displaying original or retouched image with drag-and-drop and placeholder."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setStyleSheet(
            """
            ImagePreviewCard {
                background-color: #ffffff;
                border: 2px dashed #d2d2d7;
                border-radius: 12px;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #1d1d1f;")
        layout.addWidget(self.title_label)

        self.image_label = QLabel("拖拽图片至此处\n或点击下方选择图片")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("color: #86868b; font-size: 13px;")
        layout.addWidget(self.image_label, stretch=1)

        self.info_label = QLabel("")
        self.info_label.setStyleSheet("font-size: 11px; color: #0071e3;")
        layout.addWidget(self.info_label)

    def set_image_pixmap(self, pixmap: QPixmap, info: str = "") -> None:
        scaled = pixmap.scaled(
            QSize(420, 500),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)
        self.info_label.setText(info)
        self.setStyleSheet(
            """
            ImagePreviewCard {
                background-color: #ffffff;
                border: 1px solid #e5e5ea;
                border-radius: 12px;
            }
            """
        )


class ATBDrawMainWindow(QMainWindow):
    """Main desktop application window for ATBDraw."""

    def __init__(
        self,
        completer: Optional[LatentIntentCompleter] = None,
        planner: Optional[WorkflowPlanner] = None,
        dispatcher: Optional[SlotDispatcher] = None,
        plugin: Optional[DrawPlugin] = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("ATBDraw - 意图人像精修桌面端")
        self.resize(1120, 720)

        # Core Engines
        self.plugin = plugin or DrawPlugin()
        self.plugin.initialize({"adapter": "mock"})
        self.completer = completer or LatentIntentCompleter()
        self.planner = planner or WorkflowPlanner()
        self.dispatcher = dispatcher or SlotDispatcher()

        # State
        self.current_image_path: Optional[str] = None
        self.last_draft: Optional[StructuredIntentDraft] = None
        self.last_plan: Optional[WorkflowPlan] = None
        self.last_report: Optional[WorkflowExecutionReport] = None

        self._init_ui()

    def _init_ui(self) -> None:
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_hlayout = QHBoxLayout(central_widget)
        main_hlayout.setContentsMargins(0, 0, 0, 0)
        main_hlayout.setSpacing(0)

        # Left / Center main workspace
        workspace = QWidget()
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(18, 16, 18, 16)
        workspace_layout.setSpacing(14)

        # Top Bar (Header & Actions)
        top_bar = QHBoxLayout()
        app_title = QLabel("ATBDraw 智能人像精修")
        app_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1d1d1f;")
        top_bar.addWidget(app_title)
        top_bar.addStretch()

        self.select_file_btn = QPushButton("选择本地图片 📁")
        self.select_file_btn.clicked.connect(self._on_select_file)
        top_bar.addWidget(self.select_file_btn)

        self.save_btn = QPushButton("另存为 💾")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._on_save_file)
        top_bar.addWidget(self.save_btn)
        workspace_layout.addLayout(top_bar)

        # Center Previews (Split Before / After)
        previews_layout = QHBoxLayout()
        self.before_card = ImagePreviewCard("修前原图 (Before)")
        self.after_card = ImagePreviewCard("修后效果 (After)")
        previews_layout.addWidget(self.before_card, stretch=1)
        previews_layout.addWidget(self.after_card, stretch=1)
        workspace_layout.addLayout(previews_layout, stretch=1)

        # Bottom Prompt Bar
        prompt_bar = QHBoxLayout()
        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("输入模糊修图意图（如：把右边的人稍微变瘦，衣服别走样）")
        self.prompt_input.setFixedHeight(44)
        self.prompt_input.setStyleSheet(
            """
            QLineEdit {
                border: 1px solid #d2d2d7;
                border-radius: 10px;
                padding: 0 14px;
                font-size: 14px;
                background-color: #ffffff;
            }
            QLineEdit:focus {
                border: 2px solid #0071e3;
            }
            """
        )
        self.prompt_input.returnPressed.connect(self._on_generate)
        prompt_bar.addWidget(self.prompt_input, stretch=1)

        self.generate_btn = QPushButton("心眼生成 ✨")
        self.generate_btn.setFixedHeight(44)
        self.generate_btn.setFixedWidth(130)
        self.generate_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #0071e3;
                color: #ffffff;
                font-size: 14px;
                font-weight: 600;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #0077ed;
            }
            """
        )
        self.generate_btn.clicked.connect(self._on_generate)
        prompt_bar.addWidget(self.generate_btn)
        workspace_layout.addLayout(prompt_bar)

        main_hlayout.addWidget(workspace, stretch=1)

        # Right Side Drawer
        self.drawer = ResultTuningDrawer(parent=self)
        self.drawer.refine_requested.connect(self._on_refine_requested)
        main_hlayout.addWidget(self.drawer)

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪 - 请拖入或选择图片")

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path and Path(file_path).is_file():
                self.load_image(file_path)
                break

    def _on_select_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择人像图片", "", "图片文件 (*.png *.jpg *.jpeg *.webp)"
        )
        if file_path:
            self.load_image(file_path)

    def load_image(self, file_path: str) -> None:
        self.current_image_path = file_path
        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            self.before_card.set_image_pixmap(pixmap, f"源文件: {Path(file_path).name}")
            self.status_bar.showMessage(f"已加载图片: {file_path}")
        else:
            self.status_bar.showMessage(f"已设置模拟图像路径: {Path(file_path).name}")

    def _on_generate(self) -> None:
        prompt = self.prompt_input.text().strip()
        if not prompt:
            self.status_bar.showMessage("请输入修图意图描述")
            return

        image_path = self.current_image_path or "sample_portrait.png"
        self.status_bar.showMessage("正在进行心眼意图理解与工作流规划...")

        # 1. Layer 1: Context Entity Extraction & Intent Completion
        entities = self.plugin.extract_context_entities(image_path)
        draft = self.completer.complete_intent(
            user_prompt=prompt,
            plugin=self.plugin,
            context_entities=entities,
        )
        self.last_draft = draft

        # 2. Layer 2: Workflow Planner
        templates = self.plugin.get_templates()
        plan = self.planner.plan_workflow(draft=draft, available_templates=templates)
        self.last_plan = plan

        # 3. Layer 3: Slot Dispatcher
        report = self.dispatcher.dispatch_workflow(
            plan=plan,
            plugin=self.plugin,
            draft=draft,
            initial_context={"input_image": image_path},
        )
        self.last_report = report
        self._apply_execution_report(report)

    def _on_refine_requested(self, overrides: Dict[str, Any]) -> None:
        """Triggered when user adjusts sliders and clicks '微调重新生成'."""
        if not self.last_plan:
            return

        self.status_bar.showMessage("正在直连调度层微调重跑...")
        image_path = self.current_image_path or "sample_portrait.png"

        # Direct Layer 3 re-dispatch without calling LLM
        report = self.dispatcher.dispatch_workflow(
            plan=self.last_plan,
            plugin=self.plugin,
            draft=self.last_draft,
            initial_context={"input_image": image_path},
            user_overrides=overrides,
        )
        self.last_report = report
        self._apply_execution_report(report)
        self.status_bar.showMessage(f"微调完成！已应用 {len(overrides)} 项参数调整")

    def _apply_execution_report(self, report: WorkflowExecutionReport) -> None:
        if not report.success:
            self.status_bar.showMessage("生成失败，请重试")
            return

        # Update Side Drawer with executed templates and final bound slots
        self.drawer.populate_steps(report.executed_steps)

        # Update After preview card
        final_asset = report.final_output.get("rendered_asset", "result.png")
        image_bytes = report.final_output.get("image_bytes")
        if image_bytes:
            pix = QPixmap()
            pix.loadFromData(image_bytes)
            self.after_card.set_image_pixmap(pix, f"产物: {final_asset}")
        else:
            self.after_card.info_label.setText(f"渲染产物: {final_asset}")

        self.save_btn.setEnabled(True)
        self.status_bar.showMessage(
            f"心眼生成完成 (耗时: {report.total_execution_time_ms:.1f}ms, {len(report.executed_steps)} 步骤)"
        )

    def _on_save_file(self) -> None:
        save_path, _ = QFileDialog.getSaveFileName(
            self, "另存精修图片", "retouched_portrait.png", "PNG 图像 (*.png)"
        )
        if save_path and self.last_report:
            img_bytes = self.last_report.final_output.get("image_bytes")
            if img_bytes:
                Path(save_path).write_bytes(img_bytes)
                self.status_bar.showMessage(f"已保存至: {save_path}")


def main() -> None:
    app = QApplication(sys.argv)
    window = ATBDrawMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
