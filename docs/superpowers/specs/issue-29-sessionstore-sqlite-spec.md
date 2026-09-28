# Issue #29 — SessionStore SQLite Persistence & Cascading Cleanup — Design Specification

- **Issue**: #29
- **Branch**: `agent/issue-29-sessionstore-sqlite-persistence`
- **Status**: Approved
- **Date**: 2026-09-29
- **Reference**: `docs/superpowers/specs/2026-09-29-atbmind-ui-redesign-design.md` §4.1

---

## 1. Problem Statement

ATBMind's multi-session, multi-turn message flow requires a durable persistence layer. Currently no session or message history is stored — everything is lost on restart. This spec defines `SessionStore`, the M1 storage milestone that establishes the SQLite foundation for sessions and messages with cascading physical image cleanup.

---

## 2. Design Decisions (90% Autonomous Rule Applied)

| Decision | Choice | Rationale |
|---|---|---|
| Database location | `data/atbmind.db` (file-backed) or `:memory:` (test mode) | Matches `TemplateStore` pattern; WAL mode already proven in project |
| Module location | `atbmind_core/storage/session_store.py` | Consistent with existing `atbmind_core/storage/db.py` layout |
| Schema models | Pydantic v2 in `atbmind_core/plugins/schemas.py` | Same file as all other domain models in the project |
| Primary key type | `TEXT` UUID (caller-supplied) | Decouples storage from ID generation; aligns with spec §4.1 |
| Timestamp type | `REAL` (Unix epoch float) | Direct mapping to Python `time.time()`; supports fractional seconds; matches spec SQL DDL |
| JSON fields | `plugin_state` (TEXT/JSON), `plugin_payload` (TEXT/JSON) | Schema-less plugin extensibility; encode/decode at boundary only |
| Image safety check | `Path(p).resolve().is_relative_to(generated_images_dir.resolve())` | Strict containment check prevents accidental deletion of external user files |
| Cascading delete strategy | Collect paths → delete files → DELETE DB row (ON DELETE CASCADE for messages) | Files deleted before DB rows so DB stays consistent even if file deletion partially fails |
| Thread safety | `check_same_thread=False` + WAL mode | Main thread owns all writes (per arch spec §5.2); WAL handles concurrent reads |
| Storage `__init__` export | Export `SessionStore` from `atbmind_core/storage/__init__.py` | Mirrors how `TemplateStore` is used |

---

## 3. Data Model

### 3.1 Pydantic Models (to be added to `atbmind_core/plugins/schemas.py`)

```python
class SessionRecord(BaseModel):
    session_id: str
    title: str = "新对话"
    active_plugin_id: Optional[str] = None
    plugin_state: Dict[str, Any] = Field(default_factory=dict)
    created_at: float
    updated_at: float

class MessageRecord(BaseModel):
    message_id: str
    session_id: str
    role: str  # 'user' | 'assistant' | 'system'
    content: str
    attachment_path: Optional[str] = None
    plugin_id: Optional[str] = None
    plugin_payload: Optional[Dict[str, Any]] = None
    created_at: float
```

### 3.2 SQLite Schema

```sql
-- sessions table
CREATE TABLE IF NOT EXISTS sessions (
    session_id   TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    active_plugin_id TEXT,
    plugin_state TEXT,           -- JSON blob
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC);

-- messages table
CREATE TABLE IF NOT EXISTS messages (
    message_id      TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    attachment_path TEXT,
    plugin_id       TEXT,
    plugin_payload  TEXT,        -- JSON blob
    created_at      REAL NOT NULL,
    FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_messages_session_time ON messages(session_id, created_at ASC);
```

---

## 4. SessionStore API

```python
class SessionStore:
    def __init__(self, db_path: str | Path = ":memory:",
                 generated_images_dir: str | Path = "data/generated_images") -> None: ...

    # Session CRUD
    def create_session(self, record: SessionRecord) -> SessionRecord: ...
    def get_session(self, session_id: str) -> Optional[SessionRecord]: ...
    def list_sessions(self) -> List[SessionRecord]: ...          # sorted by updated_at DESC
    def update_session_title(self, session_id: str, title: str) -> bool: ...
    def update_session_plugin_state(self, session_id: str,
                                    active_plugin_id: Optional[str],
                                    plugin_state: Dict[str, Any]) -> bool: ...
    def delete_session(self, session_id: str) -> bool: ...      # cascading file + DB cleanup

    # Message CRUD
    def append_message(self, record: MessageRecord) -> MessageRecord: ...
    def list_messages(self, session_id: str) -> List[MessageRecord]: ...  # sorted by created_at ASC

    def close(self) -> None: ...
```

---

## 5. Cascading Delete Contract

`delete_session(session_id)`:
1. Fetch all `attachment_path` and `plugin_payload` JSON for the session's messages.
2. Extract `plugin_payload["after_img"]` and `plugin_payload["before_img"]` if present.
3. For each collected path: if it resolves inside `generated_images_dir`, delete the file silently (ignore missing).
4. Execute `DELETE FROM sessions WHERE session_id = ?` — FK cascade deletes messages.

---

## 6. Acceptance Criteria

- [ ] `SessionStore` initializes schema without error for both `:memory:` and file-backed SQLite.
- [ ] Session CRUD persists across store re-instantiation (file-backed).
- [ ] `list_sessions()` returns sessions sorted `updated_at DESC`.
- [ ] `list_messages()` returns messages sorted `created_at ASC`.
- [ ] `delete_session()` deletes associated image files inside `generated_images_dir` only.
- [ ] `delete_session()` does NOT delete files outside `generated_images_dir`.
- [ ] Deleting a session cascades to delete all its messages.
- [ ] `tests/test_session_store.py` passes with 100% coverage.
