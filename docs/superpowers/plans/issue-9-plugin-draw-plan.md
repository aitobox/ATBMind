# Issue #9 Plan: 实现 ATBMind-Draw 插件基础架构与上下文实体分析器

## Implementation Steps
1. **TDD Test Suite (`tests/test_plugin_draw.py`)**:
   - 测试 `PluginRegistry.scan_directory("plugins")` 自动发现并注册 `plugin_id="draw"`。
   - 测试 `DrawVisionExtractor` / `DrawPlugin.extract_context_entities()` 对不同输入（图片路径、字典载荷、空输入）提取主体位置 (`entities`)、区域 Mask 占位 (`masks`) 与场景分析 (`scene_analysis`)。
   - 测试 `DrawPlugin.get_domain_prompt_injection()` 包含人像塑形防畸变、肤质保留纹理等潜需求领域规则。
   - 测试 `DrawPlugin.get_templates()` 与 `DrawPlugin.execute_workflow_step()` 的完整执行契约。
2. **Vision Extractor (`plugins/draw/vision/extractor.py`)**:
   - 实现 `DrawVisionExtractor` 类及 `extract()` 方法。
3. **Domain Prompt Injection (`plugins/draw/prompts/injection.py`)**:
   - 实现 `DRAW_DOMAIN_PROMPT_INJECTION` 及 `get_draw_domain_prompt_injection()`。
4. **DrawPlugin (`plugins/draw/plugin.py`)**:
   - 实现继承自 `ATBMindPlugin` 的 `DrawPlugin`，组装 `DrawVisionExtractor`、领域提示词与核心模板库。
5. **Verification**:
   - 运行 `PYTHONPATH=. conda run -n ATBMind pytest tests/` 确保全部测试通过。
