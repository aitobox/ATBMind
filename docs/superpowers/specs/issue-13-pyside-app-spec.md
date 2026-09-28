# Issue #13 Spec: 开发基于 PySide6 的极简桌面应用与结果侧微调抽屉

## 1. 目标 (Objective)
开发首个应用客户端 `ATBDraw` 桌面端应用 (`apps/atb_draw_desktop/main.py`)，基于 PySide6 实现极简图片拖拽传图、自然语言“心眼生成”触发出图以及侧边参数抽屉二次微调的完整人机协同闭环。

## 2. 界面与交互架构
1. **主窗口 (`ATBDrawMainWindow`)**:
   - macOS 原生极简浅色/深色自适应毛玻璃设计风格。
   - 上半区 / 预览区 (`PreviewArea`)：支持图片拖拽拖入 (`dragEnterEvent` / `dropEvent`) 与点击选择，展示原图与精修后图。
   - 底部控制条 (`PromptBar`)：单行自然语言输入框（如“把右边的人稍微变瘦，衣服别走样”）、“心眼生成”触发按钮以及加载状态指示器。
   - 状态栏与导出：支持修后图一键“另存为”。
2. **侧边参数微调抽屉 (`ResultTuningDrawer`)**:
   - 抽屉平时折叠或停靠在右侧，在生成成功后自动展示调用的模板清单及关键参数滑块（如形变强度 `intensity: 15%`、磨皮程度 `smooth_strength: 45%`、服装保护比例 `preserve_ratio: 85%`）。
   - 用户拖动滑块调节后，点击“微调重新生成”按钮，系统直接携带 `user_overrides` 调用 Layer 3 `SlotDispatcher`，无须重新请求大模型，实现毫秒级即时重新渲染与画布更新。
3. **集成核心引擎**:
   - 组装 `PluginRegistry`、`DrawPlugin`、`LatentIntentCompleter`、`WorkflowPlanner`、`SlotDispatcher`。
   - 默认启用 `MockImageAdapter`，离线无需 GPU 即可完成完整出图闭环。

## 3. 测试与验证设计
- 使用 `pytest-qt` (`qtbot`) 编写 `tests/test_pyside_app.py`：
  - 测试窗口初始化与控件层级结构。
  - 测试输入指令触发全流程生成并更新画布。
  - 测试侧边抽屉滑块修改与直连 Layer 3 重跑逻辑。
