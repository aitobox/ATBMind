# Issue #9 Spec: 实现 ATBMind-Draw 插件基础架构与上下文实体分析器

## 1. 目标 (Objective)
搭建首发插件 `ATBMind-Draw` 的骨架，实现图像领域专属的上下文实体提取 (`plugins/draw/vision/extractor.py`)、领域提示词注入 (`plugins/draw/prompts/injection.py`) 以及 `DrawPlugin` 核心类 (`plugins/draw/plugin.py`)，使其能被 `PluginRegistry` 自动发现并注册。

## 2. 核心模块设计
### 2.1 `plugins/draw/vision/extractor.py`
- `DrawVisionExtractor`:
  - `extract(raw_input: Any) -> Dict[str, Any]`
  - 支持多种输入格式（图像路径字符串、`Path`、字节流、字典上下文或 PIL Image 对象）。
  - 提取并返回标准化视觉上下文元数据：
    - `entities`: 主体实体列表（如 `[{"id": "person_0", "type": "portrait_subject", "bbox": [0.18, 0.08, 0.82, 0.95], "confidence": 0.96, "attributes": {...}}]`）
    - `masks`: 区域遮罩占位与语义分割描述（`face_mask`, `body_mask`, `skin_mask`, `clothing_mask`, `background_mask`）
    - `scene_analysis`: 场景光照、构图、分辨率及画质基础评估

### 2.2 `plugins/draw/prompts/injection.py`
- `DRAW_DOMAIN_PROMPT_INJECTION` 常量与 `get_draw_domain_prompt_injection() -> str` 函数：
  - 定义人像精修与图像处理的潜需求推导常识规则：
    1. 形体塑形（瘦身/拉腿/瘦腰/直角肩）自动补充服装边缘防畸变保护 (`clothing_protection`) 与背景网格防拉扯锁定 (`background_lock`)。
    2. 面部精修（瘦脸/下颌线/五官微调）自动关联颈部平滑过渡与面部光影一致性。
    3. 肤质美化（磨皮/祛痘/美白/去油光）默认保留原生皮肤微纹理与眼神光保护 (`preserve_skin_texture=True`)。
    4. 提供标准参数缺省安全阈值（如形变强度 `intensity` 默认 `0.12~0.18`，避免过度失真）。

### 2.3 `plugins/draw/plugin.py`
- `DrawPlugin(ATBMindPlugin)`:
  - `plugin_id`: `"draw"`
  - `version`: `"1.0.0"`
  - `initialize(config)`：加载默认内置种子模板与视觉提取器配置
  - `get_templates()`：返回内置核心精修模板列表（后续与 SQLite/种子库无缝衔接）
  - `extract_context_entities(raw_input)`：委托 `DrawVisionExtractor` 完成实体与遮罩提取
  - `get_domain_prompt_injection()`：返回 `get_draw_domain_prompt_injection()`
  - `execute_workflow_step(step, context)`：执行单步图像精修模板并返回 `WorkflowResult`
