"""
Tests for atbmind_core.storage.session_store.SessionStore
Covers: schema init, session CRUD, message CRUD, cascading delete with file cleanup.
100% coverage target as per Issue #29 acceptance criteria.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

import pytest

from atbmind_core.storage.schemas import MessageRecord, SessionRecord
from atbmind_core.storage.session_store import SessionStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _new_session(title: str = "Test Session", plugin_id: str | None = None) -> SessionRecord:
    now = time.time()
    return SessionRecord(
        session_id=str(uuid.uuid4()),
        title=title,
        active_plugin_id=plugin_id,
        plugin_state={},
        created_at=now,
        updated_at=now,
    )


def _new_message(session_id: str, role: str = "user", content: str = "hello") -> MessageRecord:
    return MessageRecord(
        message_id=str(uuid.uuid4()),
        session_id=session_id,
        role=role,
        content=content,
        created_at=time.time(),
    )


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------

class TestSchemaInit:
    def test_schema_init_memory(self):
        """SessionStore initializes in-memory without error."""
        store = SessionStore(":memory:")
        store.close()

    def test_schema_init_file(self, tmp_path):
        """SessionStore creates a file-backed DB with correct tables."""
        db_file = tmp_path / "atbmind.db"
        store = SessionStore(db_file)

        # Verify tables exist via sqlite_master
        conn = store._conn
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table';"
            ).fetchall()
        }
        assert "sessions" in tables
        assert "messages" in tables
        store.close()

    def test_wal_mode_enabled(self):
        """WAL journal mode is set on initialisation."""
        store = SessionStore(":memory:")
        row = store._conn.execute("PRAGMA journal_mode;").fetchone()
        # In-memory always reports 'memory', file-backed reports 'wal' — both acceptable.
        assert row[0] in ("wal", "memory")
        store.close()


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------

class TestSessionCRUD:
    def test_create_and_get_session(self):
        store = SessionStore(":memory:")
        record = _new_session("My Session")
        created = store.create_session(record)

        assert created.session_id == record.session_id
        assert created.title == "My Session"

        fetched = store.get_session(record.session_id)
        assert fetched is not None
        assert fetched.session_id == record.session_id
        assert fetched.title == "My Session"
        store.close()

    def test_get_session_not_found(self):
        store = SessionStore(":memory:")
        result = store.get_session("nonexistent-id")
        assert result is None
        store.close()

    def test_list_sessions_sorted_by_updated_at_desc(self):
        store = SessionStore(":memory:")

        older = _new_session("Older")
        older = older.model_copy(update={"updated_at": time.time() - 100})

        newer = _new_session("Newer")
        newer = newer.model_copy(update={"updated_at": time.time()})

        # Insert older first, then newer — list should return newer first
        store.create_session(older)
        store.create_session(newer)

        sessions = store.list_sessions()
        assert len(sessions) == 2
        assert sessions[0].title == "Newer"
        assert sessions[1].title == "Older"
        store.close()

    def test_update_session_title(self):
        store = SessionStore(":memory:")
        record = _new_session("Original Title")
        store.create_session(record)

        original_updated_at = record.updated_at
        time.sleep(0.01)  # ensure updated_at increases

        result = store.update_session_title(record.session_id, "New Title")
        assert result is True

        fetched = store.get_session(record.session_id)
        assert fetched is not None
        assert fetched.title == "New Title"
        assert fetched.updated_at > original_updated_at
        store.close()

    def test_update_session_title_nonexistent(self):
        store = SessionStore(":memory:")
        result = store.update_session_title("ghost-id", "Whatever")
        assert result is False
        store.close()

    def test_update_session_plugin_state(self):
        store = SessionStore(":memory:")
        record = _new_session()
        store.create_session(record)

        plugin_state = {"model": "Seedream 4.5", "aspect_ratio": "1:1"}
        time.sleep(0.01)
        result = store.update_session_plugin_state(
            record.session_id, "draw", plugin_state
        )
        assert result is True

        fetched = store.get_session(record.session_id)
        assert fetched is not None
        assert fetched.active_plugin_id == "draw"
        assert fetched.plugin_state["model"] == "Seedream 4.5"
        assert fetched.updated_at > record.updated_at
        store.close()

    def test_update_session_plugin_state_nonexistent(self):
        store = SessionStore(":memory:")
        result = store.update_session_plugin_state("ghost-id", None, {})
        assert result is False
        store.close()

    def test_delete_session_basic(self):
        store = SessionStore(":memory:")
        record = _new_session()
        store.create_session(record)

        # Append a message so we can verify cascade
        msg = _new_message(record.session_id)
        store.append_message(msg)

        deleted = store.delete_session(record.session_id)
        assert deleted is True
        assert store.get_session(record.session_id) is None
        # Messages should be cascaded
        assert store.list_messages(record.session_id) == []
        store.close()

    def test_delete_session_returns_false_for_missing(self):
        store = SessionStore(":memory:")
        result = store.delete_session("no-such-session")
        assert result is False
        store.close()


# ---------------------------------------------------------------------------
# Message CRUD
# ---------------------------------------------------------------------------

class TestMessageCRUD:
    def test_append_and_list_messages(self):
        store = SessionStore(":memory:")
        session = _new_session()
        store.create_session(session)

        m1 = _new_message(session.session_id, "user", "hello")
        m1 = m1.model_copy(update={"created_at": time.time() - 10})
        m2 = _new_message(session.session_id, "assistant", "world")
        m2 = m2.model_copy(update={"created_at": time.time()})

        store.append_message(m1)
        store.append_message(m2)

        messages = store.list_messages(session.session_id)
        assert len(messages) == 2
        assert messages[0].content == "hello"
        assert messages[1].content == "world"
        store.close()

    def test_list_messages_session_isolation(self):
        store = SessionStore(":memory:")
        s1 = _new_session("S1")
        s2 = _new_session("S2")
        store.create_session(s1)
        store.create_session(s2)

        store.append_message(_new_message(s1.session_id, content="for s1"))
        store.append_message(_new_message(s2.session_id, content="for s2"))

        assert len(store.list_messages(s1.session_id)) == 1
        assert store.list_messages(s1.session_id)[0].content == "for s1"
        assert len(store.list_messages(s2.session_id)) == 1
        store.close()

    def test_plugin_payload_roundtrip(self):
        store = SessionStore(":memory:")
        session = _new_session()
        store.create_session(session)

        payload = {
            "before_img": "/tmp/before.png",
            "after_img": "/some/path/generated_images/after.png",
            "elapsed_seconds": 1.23,
        }
        msg = MessageRecord(
            message_id=str(uuid.uuid4()),
            session_id=session.session_id,
            role="assistant",
            content="Done",
            plugin_id="draw",
            plugin_payload=payload,
            created_at=time.time(),
        )
        store.append_message(msg)

        messages = store.list_messages(session.session_id)
        assert len(messages) == 1
        assert messages[0].plugin_payload is not None
        assert messages[0].plugin_payload["before_img"] == "/tmp/before.png"
        assert abs(messages[0].plugin_payload["elapsed_seconds"] - 1.23) < 1e-6
        store.close()


# ---------------------------------------------------------------------------
# Cascading file cleanup on delete_session
# ---------------------------------------------------------------------------

class TestCascadingFileCleanup:
    def test_delete_session_cleans_generated_images(self, tmp_path):
        """Files inside generated_images_dir are deleted when session is deleted."""
        img_dir = tmp_path / "generated_images"
        img_dir.mkdir()

        # Create a fake generated image
        img_file = img_dir / f"{uuid.uuid4()}.png"
        img_file.write_bytes(b"PNG_DATA")

        store = SessionStore(":memory:", generated_images_dir=img_dir)
        session = _new_session()
        store.create_session(session)

        msg = MessageRecord(
            message_id=str(uuid.uuid4()),
            session_id=session.session_id,
            role="assistant",
            content="Result",
            plugin_payload={"after_img": str(img_file)},
            created_at=time.time(),
        )
        store.append_message(msg)

        store.delete_session(session.session_id)

        assert not img_file.exists(), "Generated image should be deleted"
        store.close()

    def test_delete_session_cleans_attachment_path(self, tmp_path):
        """attachment_path files inside generated_images_dir are also deleted."""
        img_dir = tmp_path / "generated_images"
        img_dir.mkdir()

        img_file = img_dir / "attach.png"
        img_file.write_bytes(b"ATTACH_DATA")

        store = SessionStore(":memory:", generated_images_dir=img_dir)
        session = _new_session()
        store.create_session(session)

        msg = MessageRecord(
            message_id=str(uuid.uuid4()),
            session_id=session.session_id,
            role="user",
            content="Here is my image",
            attachment_path=str(img_file),
            created_at=time.time(),
        )
        store.append_message(msg)

        store.delete_session(session.session_id)
        assert not img_file.exists(), "Attachment inside generated_images_dir should be deleted"
        store.close()

    def test_delete_session_does_not_delete_external_files(self, tmp_path):
        """Files outside generated_images_dir are NOT deleted."""
        img_dir = tmp_path / "generated_images"
        img_dir.mkdir()
        external_dir = tmp_path / "user_photos"
        external_dir.mkdir()

        external_file = external_dir / "original.jpg"
        external_file.write_bytes(b"USER_PHOTO")

        store = SessionStore(":memory:", generated_images_dir=img_dir)
        session = _new_session()
        store.create_session(session)

        msg = MessageRecord(
            message_id=str(uuid.uuid4()),
            session_id=session.session_id,
            role="user",
            content="My photo",
            attachment_path=str(external_file),
            created_at=time.time(),
        )
        store.append_message(msg)

        store.delete_session(session.session_id)
        assert external_file.exists(), "External user file must NOT be deleted"
        store.close()

    def test_delete_session_tolerates_missing_file(self, tmp_path):
        """If a referenced image file has already been deleted, delete_session doesn't raise."""
        img_dir = tmp_path / "generated_images"
        img_dir.mkdir()

        nonexistent = img_dir / "gone.png"  # never created

        store = SessionStore(":memory:", generated_images_dir=img_dir)
        session = _new_session()
        store.create_session(session)

        msg = MessageRecord(
            message_id=str(uuid.uuid4()),
            session_id=session.session_id,
            role="assistant",
            content="Result",
            plugin_payload={"after_img": str(nonexistent)},
            created_at=time.time(),
        )
        store.append_message(msg)

        # Must not raise
        result = store.delete_session(session.session_id)
        assert result is True
        store.close()


# ---------------------------------------------------------------------------
# Persistence across re-instantiation
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_persist_across_reinstantiation(self, tmp_path):
        """File-backed sessions and messages survive closing and reopening the store."""
        db_file = tmp_path / "atbmind.db"

        # Write data
        store1 = SessionStore(db_file)
        session = _new_session("Persisted Session")
        store1.create_session(session)
        msg = _new_message(session.session_id, content="persistent message")
        store1.append_message(msg)
        store1.close()

        # Read data from fresh instance
        store2 = SessionStore(db_file)
        fetched = store2.get_session(session.session_id)
        assert fetched is not None
        assert fetched.title == "Persisted Session"

        messages = store2.list_messages(session.session_id)
        assert len(messages) == 1
        assert messages[0].content == "persistent message"
        store2.close()


# ---------------------------------------------------------------------------
# Additional edge cases (identified during auto-review)
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_list_sessions_empty(self):
        """list_sessions returns an empty list when no sessions exist."""
        store = SessionStore(":memory:")
        result = store.list_sessions()
        assert result == []
        store.close()

    def test_list_messages_empty(self):
        """list_messages returns empty list for session with no messages."""
        store = SessionStore(":memory:")
        session = _new_session()
        store.create_session(session)
        messages = store.list_messages(session.session_id)
        assert messages == []
        store.close()

    def test_close_is_idempotent(self):
        """Calling close() multiple times does not raise."""
        store = SessionStore(":memory:")
        store.close()
        store.close()  # Must not raise
