# Issue #5 Plan: 实现通用模板元数据本地存储与索引管理 (SQLite)

## Implementation Steps
1. **TDD Test Suite (`tests/test_storage_db.py`)**:
   - 测试 `:memory:` 模式与文件持久化模式的数据库初始化与增删改查。
   - 测试 `upsert_templates` 对 1,000 条模板的批量导入性能（耗时 `< 100ms`）与幂等更新行为。
   - 测试 `query_templates` 按 `plugin_id`、`category`、`target_scope` 和 `keyword` 分箱过滤。
2. **Storage Engine (`atbmind_core/storage/db.py`)**:
   - 实现 `TemplateStore` (别名 `TemplateDatabase`)，创建 `templates` 表与复合索引，支持批量 `upsert_templates` 与多维分箱查询。
3. **Verification**:
   - 运行 `PYTHONPATH=. conda run -n ATBMind pytest tests/` 确保全部测试通过。
