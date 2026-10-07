"""
ATBMind Universal Template Metadata SQLite Storage & Index Manager
Provides zero-configuration in-memory or file-backed SQLite indexing with sub-10ms bulk upserts and bucketed queries.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import List, Optional, Sequence

from atbmind_core.storage.schemas import TemplateMetadata


class TemplateStore:
    """
    Lightweight SQLite database manager for ATBMind plugin template metadata.
    Supports both ':memory:' and persistent local file paths.
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA synchronous=NORMAL;")
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS templates (
                    plugin_id TEXT NOT NULL,
                    template_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    keywords TEXT NOT NULL,
                    target_scope TEXT NOT NULL,
                    slot_definitions TEXT NOT NULL,
                    dependencies TEXT NOT NULL,
                    PRIMARY KEY (plugin_id, template_id)
                );
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_templates_plugin_category ON templates(plugin_id, category);"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_templates_plugin_scope ON templates(plugin_id, target_scope);"
            )

    def upsert_templates(self, plugin_id: str, templates: Sequence[TemplateMetadata]) -> int:
        """
        Bulk insert or update template metadata records inside a single transaction.
        """
        if not templates:
            return 0

        rows = [
            (
                plugin_id,
                tpl.template_id,
                tpl.name,
                tpl.category,
                json.dumps(tpl.keywords, ensure_ascii=False),
                tpl.target_scope,
                json.dumps(tpl.slot_definitions, ensure_ascii=False),
                json.dumps(tpl.dependencies, ensure_ascii=False),
            )
            for tpl in templates
        ]

        with self._conn:
            self._conn.executemany(
                """
                INSERT INTO templates (
                    plugin_id, template_id, name, category, keywords, target_scope, slot_definitions, dependencies
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(plugin_id, template_id) DO UPDATE SET
                    name = excluded.name,
                    category = excluded.category,
                    keywords = excluded.keywords,
                    target_scope = excluded.target_scope,
                    slot_definitions = excluded.slot_definitions,
                    dependencies = excluded.dependencies;
                """,
                rows,
            )
        return len(rows)

    def _row_to_model(self, row: sqlite3.Row) -> TemplateMetadata:
        return TemplateMetadata(
            template_id=row["template_id"],
            name=row["name"],
            category=row["category"],
            keywords=json.loads(row["keywords"]),
            target_scope=row["target_scope"],
            slot_definitions=json.loads(row["slot_definitions"]),
            dependencies=json.loads(row["dependencies"]),
        )

    def get_template(self, plugin_id: str, template_id: str) -> Optional[TemplateMetadata]:
        cursor = self._conn.execute(
            "SELECT * FROM templates WHERE plugin_id = ? AND template_id = ?;",
            (plugin_id, template_id),
        )
        row = cursor.fetchone()
        return self._row_to_model(row) if row else None

    def query_templates(
        self,
        plugin_id: str,
        category: Optional[str] = None,
        target_scope: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[TemplateMetadata]:
        clauses = ["plugin_id = ?"]
        params: List[object] = [plugin_id]

        if category:
            clauses.append("category = ?")
            params.append(category)
        if target_scope:
            clauses.append("target_scope = ?")
            params.append(target_scope)
        if keyword:
            clauses.append("(keywords LIKE ? OR name LIKE ?)")
            like_val = f"%{keyword}%"
            params.extend([like_val, like_val])

        sql = f"SELECT * FROM templates WHERE {' AND '.join(clauses)} ORDER BY template_id ASC"
        if limit is not None and limit > 0:
            sql += " LIMIT ?"
            params.append(int(limit))

        cursor = self._conn.execute(sql, params)
        return [self._row_to_model(r) for r in cursor.fetchall()]

    def delete_template(self, plugin_id: str, template_id: str) -> bool:
        with self._conn:
            cursor = self._conn.execute(
                "DELETE FROM templates WHERE plugin_id = ? AND template_id = ?;",
                (plugin_id, template_id),
            )
        return cursor.rowcount > 0

    def clear_plugin_templates(self, plugin_id: str) -> int:
        with self._conn:
            cursor = self._conn.execute(
                "DELETE FROM templates WHERE plugin_id = ?;",
                (plugin_id,),
            )
        return cursor.rowcount

    def count_templates(self, plugin_id: Optional[str] = None) -> int:
        if plugin_id:
            cursor = self._conn.execute(
                "SELECT COUNT(*) AS cnt FROM templates WHERE plugin_id = ?;",
                (plugin_id,),
            )
        else:
            cursor = self._conn.execute("SELECT COUNT(*) AS cnt FROM templates;")
        row = cursor.fetchone()
        return int(row["cnt"]) if row else 0

    def close(self) -> None:
        if self._conn:
            self._conn.close()


TemplateDatabase = TemplateStore
