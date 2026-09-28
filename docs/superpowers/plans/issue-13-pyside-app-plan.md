# Issue #13 Plan: 开发基于 PySide6 的极简桌面应用与结果侧微调抽屉

## Implementation Steps
1. **Core Widgets & Drawer (`apps/atb_draw_desktop/drawer.py` & `apps/atb_draw_desktop/canvas.py`)**:
   - `ImageCanvas`: 支持图片拖拽上传与修前/修后对比预览。
   - `ResultTuningDrawer`: 动态渲染执行模板卡片与浮点/整型参数滑块，暴露 `get_slot_overrides()` 与 `regenerate_requested` 信号。
2. **Main Window & Pipeline Integration (`apps/atb_draw_desktop/main.py`)**:
   - `ATBDrawMainWindow`: 组装 `ImageCanvas`、`PromptBar`、`ResultTuningDrawer` 与三层引擎（`Completer -> Planner -> Dispatcher -> DrawPlugin`）。
   - 实现“心眼生成”全流程与“微调重新生成”直连 Layer 3 调度。
3. **Unit Tests (`tests/test_pyside_app.py`)**:
   - 使用 `pytest-qt` 验证窗口组件加载、生成管线执行、抽屉参数滑块更新与二次微调重跑。
4. **Verification**:
   - 运行 `PYTHONPATH=. conda run -n ATBMind pytest tests/test_pyside_app.py` 及全量测试。
