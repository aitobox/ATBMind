# Design Specification: Session Checkpoint Projection & Speaker Metadata Mapping

- **Issue**: [#77](https://github.com/aitobox/ATBMind/issues/77)
- **Parent Epic**: [#74](https://github.com/aitobox/ATBMind/issues/74)
- **Sequence**: Step 3 of 4 (AgentTeams Storage & Context Projection Layer)

---

## 1. Problem Context & Objectives
In multi-agent collaborative group chat, if every specialist's internal multi-turn tool calling, raw prompt iteration, and intermediate reasoning were directly recorded into the main room session:
1. The main room's context window would rapidly bloat and trigger premature context compaction.
2. The user experience would be cluttered with low-level execution noise rather than coherent group dialogue.
3. Message speaker identities would be ambiguous without structured metadata tagging (`speaker_role`, `speaker_name`, `avatar`).

This specification establishes the `atbmind_core/roles/projection.py` module, providing virtual sub-session key derivation, message speaker tagging, and clean turn projection from member sub-sessions to the primary room conversation.

---

## 2. Architecture & Data Structures

### 2.1 Virtual Sub-session Key Derivation
```python
def derive_member_session_id(room_session_id: str, role_id: str) -> str:
    """Derives a deterministic isolated sub-session ID for a specialist role within a room."""
    return f"{room_session_id}:member:{role_id}"

def parse_member_session_id(member_session_id: str) -> Optional[tuple[str, str]]:
    """Extracts (room_session_id, role_id) from a derived member session ID."""
```

### 2.2 Speaker Metadata Tagging
```python
def tag_message_speaker(
    msg: AgentMessage,
    speaker_role: str,
    speaker_name: Optional[str] = None,
    avatar: Optional[str] = None,
) -> AgentMessage:
    """Enriches an AgentMessage's metadata with speaker identity attributes."""
```

### 2.3 Turn Projection
```python
def project_member_turn_to_room(
    member_messages: List[AgentMessage],
    room_session_id: str,
    speaker_role: str,
    speaker_name: Optional[str] = None,
    avatar: Optional[str] = None,
) -> List[AgentMessage]:
    """Filters member execution messages, projecting only final replies and UI cards to the room."""
```

### 2.4 `TeamThreadProjection` Manager
A higher-level coordinator managing sub-session persistence (e.g. via `SessionStore`), isolating tool execution history in the sub-session, and projecting deliverables to the room session.

---

## 3. Subtask Scope Creep Guard
Strictly isolate implementation to `atbmind_core/roles/projection.py`, exports in `atbmind_core/roles/__init__.py`, and `tests/test_team_projection.py`.
Do NOT modify desktop Qt timeline rendering widgets (that is exclusively Step 4, Issue #78).

---

## 4. Implementation Task List

- [x] Task 1: Implement derive_member_session_id and parse_member_session_id in atbmind_core/roles/projection.py
- [x] Task 2: Implement tag_message_speaker and project_member_turn_to_room with metadata projection
- [x] Task 3: Implement TeamThreadProjection session coordinator supporting SessionStore isolation
- [x] Task 4: Export projection utilities in atbmind_core/roles/__init__.py
- [x] Task 5: Write comprehensive unit tests in tests/test_team_projection.py
- [x] Task 6: Run full pytest suite and verify 100% pass
- [x] Task 7: Execute grill-me audit for projection isolation and data integrity
