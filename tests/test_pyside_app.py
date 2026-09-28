from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from apps.atb_draw_desktop.main import ATBDrawMainWindow
from atbmind_core.engine.completer import LatentIntentCompleter
from atbmind_core.engine.dispatcher import SlotDispatcher
from atbmind_core.engine.planner import WorkflowPlanner
from plugins.draw.plugin import DrawPlugin
from tests.benchmarks.benchmark_draw import BenchmarkMockLLMClient


def test_atb_draw_desktop_window_init(qtbot):
    """Verify ATBDrawMainWindow initializes properly with cards, prompt input, and drawer."""
    window = ATBDrawMainWindow()
    qtbot.addWidget(window)

    assert window.windowTitle() == "ATBDraw - 意图人像精修桌面端"
    assert window.prompt_input is not None
    assert window.generate_btn is not None
    assert window.drawer is not None
    assert window.before_card is not None
    assert window.after_card is not None


def test_atb_draw_desktop_full_flow_and_drawer_refine(qtbot, tmp_path: Path):
    """Verify full loop: load image -> prompt generation -> drawer populated -> slider tweak -> Layer 3 re-dispatch."""
    # Create fake test PNG
    fake_png = tmp_path / "test_portrait.png"
    pix = QPixmap(100, 100)
    pix.fill(Qt.GlobalColor.cyan)
    pix.save(str(fake_png), "PNG")

    mock_client = BenchmarkMockLLMClient()
    completer = LatentIntentCompleter(llm_client=mock_client)
    planner = WorkflowPlanner(llm_client=mock_client)
    dispatcher = SlotDispatcher()
    plugin = DrawPlugin()
    plugin.initialize({"adapter": "mock"})

    window = ATBDrawMainWindow(
        completer=completer,
        planner=planner,
        dispatcher=dispatcher,
        plugin=plugin,
    )
    qtbot.addWidget(window)

    # 1. Load image
    window.load_image(str(fake_png))
    assert window.current_image_path == str(fake_png)

    # 2. Enter prompt and trigger generation
    window.prompt_input.setText("把右边的人稍微变瘦，衣服别走样")
    qtbot.mouseClick(window.generate_btn, Qt.MouseButton.LeftButton)

    # Verify execution report and drawer cards
    assert window.last_report is not None
    assert window.last_report.success is True
    assert len(window.last_report.executed_steps) >= 2
    assert "intensity" in window.drawer.get_slot_overrides()

    # Verify slider initial value
    initial_intensity = window.drawer.get_slot_overrides()["intensity"]
    assert initial_intensity == 0.15

    # 3. Simulate user adjusting slider in side drawer
    slider_widget = window.drawer._param_widgets["intensity"]
    slider_widget.slider.setValue(25)  # 25% = 0.25
    assert window.drawer.get_slot_overrides()["intensity"] == 0.25

    # 4. Click '微调重新生成' button in drawer
    qtbot.mouseClick(window.drawer.refine_btn, Qt.MouseButton.LeftButton)

    # Verify direct Layer 3 re-dispatch updated report without changing plan
    assert window.last_report.success is True
    assert window.last_report.executed_steps[0].slots["intensity"] == 0.25
    assert "微调完成" in window.status_bar.currentMessage()
