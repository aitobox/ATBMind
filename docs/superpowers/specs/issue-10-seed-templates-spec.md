# Issue #10 Spec: 整理并导入首期 300~500 条高频人像精修种子模板库

## 1. 目标 (Objective)
结合 `resource/ATBDraw-prompts.csv` 真实提示词数据与人像精修高频场景，构建包含 360 条标准化模板的 `plugins/draw/templates/seed_templates.json`，覆盖四大核心分类（`body_shaping`、`face_sculpting`、`skin_lighting`、`cloth_background`），并提供自动化校验与 SQLite 导入验证脚本 `scripts/validate_templates.py`。

## 2. 四大分类与联动依赖体系
1. **`body_shaping` (人像修形, 90 条)**：全身显瘦、直角肩、天鹅颈、收腰腹、长腿比例、背部薄化、手臂纤细、骨盆体态矫正等。
2. **`face_sculpting` (面部五官精修, 90 条)**：下颌线微雕、瘦脸流畅度、高颅顶/发际线、眼部神采放大、鼻梁立体度、法令纹淡化、苹果肌提拉等。
3. **`skin_lighting` (质感光影, 90 条)**：双频原生肌理磨皮、冷白皮通透感、蝴蝶光/伦勃朗补光、眼神光高光增强、暗部提亮、环境色温统一等。
4. **`cloth_background` (衣物与背景防畸变联动, 90 条)**：服装边缘刚性锁定、条纹/格纹防弯曲、背景网格透视保护、门框/地平线防拉扯、发丝边缘精细抠图保护等（作为修形与塑形模板的拓扑后置依赖或前置锁定）。

## 3. 校验脚本 (`scripts/validate_templates.py`)
- 验证模板总数在 `300 ~ 500` 之间（定为 360 条）。
- 验证每条模板符合 `TemplateMetadata` Pydantic 数据契约，且 `template_id` 100% 唯一。
- 验证所有 `dependencies` 引用的 `template_id` 均存在于模板库中且无环。
- 调用 `TemplateStore(":memory:").upsert_templates("draw", templates)` 验证毫秒级无错导入。
