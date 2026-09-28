# Issue #29 — SessionStore SQLite Persistence — Implementation Plan

- **Issue**: #29
- **Branch**: `agent/issue-29-sessionstore-sqlite-persistence`
- **Spec**: `docs/superpowers/specs/issue-29-sessionstore-sqlite-spec.md`
- **Test command**: `conda run -n ATBMind python -m pytest tests/test_session_store.py -v`
- **Full suite**: `conda run -n ATBMind python -m pytest tests/ -v`

---

## Task Sequence (TDD Order)

### Task 1 — Add `SessionRecord` and `MessageRecord` to `schemas.py`

**File**: `atbmind_core/plugins/schemas.py`

Append `SessionRecord` and `MessageRecord` Pydantic v2 models after the existing models.

**Verification**: Import succeeds without error.

---

### Task 2 — Create `atbmind_core/storage/session_store.py` (skeleton + schema init)

**File**: `atbmind_core/storage/session_store.py` (new)

Implement `SessionStore.__init__` and `_init_schema`:
- Accept `db_path` (default `:memory:`) and `generated_images_dir`.
- Open SQLite connection with WAL mode.
- Create `sessions` and `messages` tables + indexes.

---

### Task 3 — Write TDD tests (skeleton), run to confirm failure

**File**: `tests/test_session_store.py` (new)

Write full test file covering:
1. `test_schema_init_memory` — `:memory:` initialization succeeds.
2. `test_schema_init_file` — File-backed initialization creates tables.
3. `test_create_and_get_session` — Round-trip create/get.
4. `test_list_sessions_sorted_by_updated_at_desc` — Ordering guarantee.
5. `test_update_session_title` — Title mutated, `updated_at` bumped.
6. `test_update_session_plugin_state` — `active_plugin_id` + `plugin_state` updated.
7. `test_get_session_not_found` — Returns `None`.
8. `test_delete_session_basic` — Session gone after delete; messages cascaded.
9. `test_delete_session_cleans_generated_images` — Files inside `generated_images_dir` deleted.
10. `test_delete_session_does_not_delete_external_files` — Files outside dir NOT deleted.
11. `test_append_and_list_messages` — Messages sorted ASC.
12. `test_list_messages_session_isolation` — Messages scoped to session.
13. `test_persist_across_reinstantiation` — File-backed session survives store close/reopen.
14. `test_delete_session_returns_false_for_missing` — Returns `False` for unknown id.
15. `test_plugin_payload_roundtrip` — JSON payload preserved correctly.

Run: confirm all fail (module doesn't implement yet).

---

### Task 4 — Implement Session CRUD

**File**: `atbmind_core/storage/session_store.py`

Implement:
- `create_session(record: SessionRecord) -> SessionRecord`
- `get_session(session_id: str) -> Optional[SessionRecord]`
- `list_sessions() -> List[SessionRecord]` (sorted `updated_at DESC`)
- `update_session_title(session_id, title) -> bool` (also bump `updated_at`)
- `update_session_plugin_state(session_id, active_plugin_id, plugin_state) -> bool` (bump `updated_at`)

Run: Task 1–8 tests pass.

---

### Task 5 — Implement Message CRUD

**File**: `atbmind_core/storage/session_store.py`

Implement:
- `append_message(record: MessageRecord) -> MessageRecord`
- `list_messages(session_id: str) -> List[MessageRecord]` (sorted `created_at ASC`)

Run: Task 11–12 tests pass.

---

### Task 6 — Implement `delete_session` with cascading file cleanup

**File**: `atbmind_core/storage/session_store.py`

Implement:
- Collect `attachment_path` + `plugin_payload["after_img"]`/`["before_img"]` for all messages.
- For each path: check `Path(p).resolve().is_relative_to(generated_images_dir.resolve())`.
- Delete only safe files; silently ignore missing files.
- Execute `DELETE FROM sessions WHERE session_id = ?`.
- Return `True` if row was found/deleted, `False` otherwise.

Run: All tests pass.

---

### Task 7 — Export from `atbmind_core/storage/__init__.py`

**File**: `atbmind_core/storage/__init__.py`

Add: `from atbmind_core.storage.session_store import SessionStore`

---

### Task 8 — Run full test suite, verify zero regressions

```bash
conda run -n ATBMind python -m pytest tests/ -v
```

Expected: All existing tests green + new `test_session_store.py` 100% pass.

---

### Task 9 — Git commit

```bash
git add atbmind_core/plugins/schemas.py \
        atbmind_core/storage/session_store.py \
        atbmind_core/storage/__init__.py \
        tests/test_session_store.py \
        docs/superpowers/specs/issue-29-sessionstore-sqlite-spec.md \
        docs/superpowers/plans/issue-29-sessionstore-sqlite-plan.md
git commit -m "feat(storage): implement SessionStore SQLite persistence (closes #29)"
```

---

### Task 10 — Transition to `reviewing` and invoke `atb-github-code-reviewer`
