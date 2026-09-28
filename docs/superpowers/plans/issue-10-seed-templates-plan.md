# Issue #10 Plan: 整理并导入首期 300~500 条高频人像精修种子模板库

## Implementation Steps
1. **Validation & Seed Builder Script (`scripts/validate_templates.py`)**:
   - 支持从 `resource/ATBDraw-prompts.csv` 提取真实人像与摄影特征，并结合四大分类精修词库生成 360 条标准化 `TemplateMetadata` JSON (`plugins/draw/templates/seed_templates.json`)。
   - 支持命令行直接校验：`python3 scripts/validate_templates.py plugins/draw/templates/seed_templates.json`，检查数量 (`>= 300`)、ID 唯一性、槽位完整性、依赖合法性及 `TemplateStore` SQLite 导入。
2. **Generate `plugins/draw/templates/seed_templates.json`**:
   - 生成 360 条结构完整、含中英双语检索关键词与联动依赖关系的模板元数据。
3. **Integrate with `DrawPlugin` (`plugins/draw/plugin.py`)**:
   - 更新 `DrawPlugin` 初始化时自动加载 `plugins/draw/templates/seed_templates.json`（保留内置核心模板兼容）。
4. **Unit Tests (`tests/test_seed_templates.py`)**:
   - 验证 `seed_templates.json` 条目数量、四大分类覆盖率、SQLite 导入与 `DrawPlugin.get_templates()` 返回结果。
