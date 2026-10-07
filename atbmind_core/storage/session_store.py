"""
ATBMind SessionStore — SQLite-backed multi-session & multi-turn message persistence.

Manages 'sessions' and 'messages' tables in data/atbmind.db (WAL mode).
Provides full session/message CRUD with cascading physical file cleanup on delete.

Thread safety contract (per architecture spec §5.2):
  All writes are performed from the main thread. check_same_thread=False allows
  the connection to be shared but the caller must honour the single-writer rule.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from atbmind_core.storage.schemas import MessageRecord, SessionRecord


class SessionStore:
    """
    Lightweight SQLite storage manager for ATBMind sessions and messages.

    Args:
        db_path: Path to the SQLite database file, or ':memory:' for in-process testing.
        generated_images_dir: Root directory for AI-generated images.  Only files whose
            resolved path is *inside* this directory are eligible for cascading deletion
            when a session is removed.  Defaults to 'data/generated_images'.
    """

    def __init__(
        self,
        db_path: str | Path = ":memory:",
        generated_images_dir: str | Path = "data/generated_images",
    ) -> None:
        self.db_path = str(db_path)
        self._generated_images_dir = Path(generated_images_dir).resolve()

        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # Enable FK enforcement (disabled by default in SQLite)
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._init_schema()

    @property
    def generated_images_dir(self) -> Path:
        """Root directory for AI-generated images."""
        return self._generated_images_dir

    # ------------------------------------------------------------------
    # Schema initialisation
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA synchronous=NORMAL;")

            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id       TEXT PRIMARY KEY,
                    title            TEXT NOT NULL,
                    active_plugin_id TEXT,
                    plugin_state     TEXT,
                    created_at       REAL NOT NULL,
                    updated_at       REAL NOT NULL
                );
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_updated "
                "ON sessions(updated_at DESC);"
            )

            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    message_id      TEXT PRIMARY KEY,
                    session_id      TEXT NOT NULL,
                    role            TEXT NOT NULL,
                    content         TEXT NOT NULL,
                    attachment_path TEXT,
                    plugin_id       TEXT,
                    plugin_payload  TEXT,
                    created_at      REAL NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                        ON DELETE CASCADE
                );
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_session_time "
                "ON messages(session_id, created_at ASC);"
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _row_to_session(self, row: sqlite3.Row) -> SessionRecord:
        plugin_state: Dict[str, Any] = {}
        if row["plugin_state"]:
            plugin_state = json.loads(row["plugin_state"])
        return SessionRecord(
            session_id=row["session_id"],
            title=row["title"],
            active_plugin_id=row["active_plugin_id"],
            plugin_state=plugin_state,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_message(self, row: sqlite3.Row) -> MessageRecord:
        plugin_payload: Optional[Dict[str, Any]] = None
        if row["plugin_payload"]:
            plugin_payload = json.loads(row["plugin_payload"])
        return MessageRecord(
            message_id=row["message_id"],
            session_id=row["session_id"],
            role=row["role"],
            content=row["content"],
            attachment_path=row["attachment_path"],
            plugin_id=row["plugin_id"],
            plugin_payload=plugin_payload,
            created_at=row["created_at"],
        )

    def _is_in_generated_dir(self, path_str: str) -> bool:
        """Return True if `path_str` resolves to a file inside _generated_images_dir."""
        try:
            resolved = Path(path_str).resolve()
            return resolved.is_relative_to(self._generated_images_dir)
        except (ValueError, TypeError):
            return False

    def _safe_delete_file(self, path_str: Optional[str]) -> None:
        """Delete a file if it exists inside generated_images_dir; silently ignore errors."""
        if not path_str:
            return
        if self._is_in_generated_dir(path_str):
            try:
                Path(path_str).unlink(missing_ok=True)
            except OSError:
                pass  # Best-effort; never raise from cleanup

    # ------------------------------------------------------------------
    # Session CRUD
    # ------------------------------------------------------------------

    def create_session(self, record: SessionRecord) -> SessionRecord:
        """Insert a new session record. Returns the same record."""
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO sessions
                    (session_id, title, active_plugin_id, plugin_state, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    record.session_id,
                    record.title,
                    record.active_plugin_id,
                    json.dumps(record.plugin_state, ensure_ascii=False),
                    record.created_at,
                    record.updated_at,
                ),
            )
        return record

    def get_session(self, session_id: str) -> Optional[SessionRecord]:
        """Fetch a single session by ID; returns None if not found."""
        cursor = self._conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?;",
            (session_id,),
        )
        row = cursor.fetchone()
        return self._row_to_session(row) if row else None

    def list_sessions(self) -> List[SessionRecord]:
        """Return all sessions sorted by updated_at descending (newest first)."""
        cursor = self._conn.execute(
            "SELECT * FROM sessions ORDER BY updated_at DESC;"
        )
        return [self._row_to_session(r) for r in cursor.fetchall()]

    def update_session_title(self, session_id: str, title: str) -> bool:
        """
        Update a session's title and bump updated_at.
        Returns True if the session was found and updated; False otherwise.
        """
        now = time.time()
        with self._conn:
            cursor = self._conn.execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE session_id = ?;",
                (title, now, session_id),
            )
        return cursor.rowcount > 0

    def update_session_plugin_state(
        self,
        session_id: str,
        active_plugin_id: Optional[str],
        plugin_state: Dict[str, Any],
    ) -> bool:
        """
        Update the active plugin and its UI state, bumping updated_at.
        Returns True if the session was found and updated; False otherwise.
        """
        now = time.time()
        with self._conn:
            cursor = self._conn.execute(
                """
                UPDATE sessions
                   SET active_plugin_id = ?,
                       plugin_state = ?,
                       updated_at = ?
                 WHERE session_id = ?;
                """,
                (
                    active_plugin_id,
                    json.dumps(plugin_state, ensure_ascii=False),
                    now,
                    session_id,
                ),
            )
        return cursor.rowcount > 0

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and cascade-delete its messages from the database.
        Before the DB deletion, scans all message paths (attachment_path and
        plugin_payload["after_img"] / ["before_img"]) and physically removes
        any files that reside inside generated_images_dir.

        Returns True if the session existed and was deleted; False otherwise.
        """
        # --- 1. Collect all file paths associated with this session's messages ---
        cursor = self._conn.execute(
            "SELECT attachment_path, plugin_payload FROM messages WHERE session_id = ?;",
            (session_id,),
        )
        rows = cursor.fetchall()

        paths_to_clean: List[str] = []
        for row in rows:
            if row["attachment_path"]:
                paths_to_clean.append(row["attachment_path"])
            if row["plugin_payload"]:
                try:
                    payload = json.loads(row["plugin_payload"])
                    for key in ("after_img", "before_img"):
                        val = payload.get(key)
                        if val:
                            paths_to_clean.append(str(val))
                except (json.JSONDecodeError, AttributeError):
                    pass  # Malformed payload — skip

        # --- 2. Delete physical files safely (inside generated_images_dir only) ---
        for path_str in paths_to_clean:
            self._safe_delete_file(path_str)

        # --- 3. Delete the session row; FK ON DELETE CASCADE removes messages ---
        with self._conn:
            cursor = self._conn.execute(
                "DELETE FROM sessions WHERE session_id = ?;",
                (session_id,),
            )
        return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Message CRUD
    # ------------------------------------------------------------------

    def append_message(self, record: MessageRecord) -> MessageRecord:
        """Insert a new message into the session's message stream."""
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO messages
                    (message_id, session_id, role, content,
                     attachment_path, plugin_id, plugin_payload, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    record.message_id,
                    record.session_id,
                    record.role,
                    record.content,
                    record.attachment_path,
                    record.plugin_id,
                    json.dumps(record.plugin_payload, ensure_ascii=False)
                    if record.plugin_payload is not None
                    else None,
                    record.created_at,
                ),
            )
        return record

    def list_messages(self, session_id: str) -> List[MessageRecord]:
        """Return all messages for a session sorted by created_at ascending (oldest first)."""
        cursor = self._conn.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at ASC;",
            (session_id,),
        )
        return [self._row_to_message(r) for r in cursor.fetchall()]

    def get_messages(self, session_id: str) -> List[MessageRecord]:
        """Alias for list_messages."""
        return self.list_messages(session_id)

    def clear_session_messages(self, session_id: str) -> int:
        """Deletes all messages for a given session."""
        with self._conn:
            cursor = self._conn.execute(
                "DELETE FROM messages WHERE session_id = ?;",
                (session_id,),
            )
        return cursor.rowcount

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying SQLite connection. Safe to call multiple times."""
        if self._conn:
            self._conn.close()
            self._conn = None  # Prevent accidental double-close
