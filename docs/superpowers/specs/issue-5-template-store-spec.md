# Issue #5 Spec: 实现通用模板元数据本地存储与索引管理 (SQLite)

## 1. 目标 (Objective)
基于 SQLite 实现轻量化、零配置的模板元数据库 (`atbmind_core/storage/db.py`)，支持内存数据库 (`:memory:`) 与本地文件持久化模式，为各插件挂载的数万条模板提供毫秒级批量写入与分箱检索 (`plugin_id`, `category`, `target_scope`, `keyword`)。

## 2. 表结构与索引设计
- 表名：`templates`
- 字段：
  - `plugin_id TEXT NOT NULL`
  - `template_id TEXT NOT NULL`
  - `name TEXT NOT NULL`
  - `category TEXT NOT NULL`
  - `keywords TEXT NOT NULL` (JSON 序列化列表)
  - `target_scope TEXT NOT NULL`
  - `slot_definitions TEXT NOT NULL` (JSON 序列化字典)
  - `dependencies TEXT NOT NULL` (JSON 序列化列表)
  - `PRIMARY KEY (plugin_id, template_id)`
- 索引：
  - `CREATE INDEX IF NOT EXISTS idx_templates_plugin_category ON templates(plugin_id, category);`
  - `CREATE INDEX IF NOT EXISTS idx_templates_plugin_scope ON templates(plugin_id, target_scope);`

## 3. 核心接口 (`TemplateDatabase` / `TemplateStore`)
- `upsert_templates(plugin_id: str, templates: Sequence[TemplateMetadata]) -> int`: 使用单事务 `executemany` 批量插入或更新模板，1,000 条耗时 < 20ms（远低于 100ms 指标）。
- `get_template(plugin_id: str, template_id: str) -> Optional[TemplateMetadata]`
- `query_templates(plugin_id: str, category: Optional[str] = None, target_scope: Optional[str] = None, keyword: Optional[str] = None) -> List[TemplateMetadata]`
- `delete_template(plugin_id: str, template_id: str) -> bool`
- `clear_plugin_templates(plugin_id: str) -> int`
- `count_templates(plugin_id: Optional[str] = None) -> int`
