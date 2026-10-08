# Implementation Plan: Session Checkpoint Projection & Speaker Metadata Mapping

- **Issue**: [#77](https://github.com/aitobox/ATBMind/issues/77)
- **Branch**: `agent/issue-77-session-projection`
- **Spec**: `docs/superpowers/specs/issue-77-session-projection-spec.md`

---

## Task Breakdown & Verification Matrix

### Task 1: Write TDD test cases in `tests/test_team_projection.py`
- **File**: `tests/test_team_projection.py`
- **Steps**:
  1. Test `derive_member_session_id` and `parse_member_session_id` roundtrip and edge cases.
  2. Test `tag_message_speaker` updates `metadata` correctly (`speaker_role`, `speaker_name`, `avatar`).
  3. Test `project_member_turn_to_room` filters out intermediate tool calls and tool results, preserving only user instruction and final assistant deliverables.
  4. Test UI card / artifact retention during projection.
  5. Test `TeamThreadProjection` with `SessionStore` to verify sub-session isolation and room projection.
- **Verification Command**:
  `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_team_projection.py` (Must fail initially).

### Task 2: Implement `atbmind_core/roles/projection.py`
- **File**: `atbmind_core/roles/projection.py`
- **Steps**:
  1. Define `derive_member_session_id(room_session_id: str, role_id: str) -> str`.
  2. Define `parse_member_session_id(member_session_id: str) -> Optional[tuple[str, str]]`.
  3. Define `tag_message_speaker(msg: AgentMessage, speaker_role: str, speaker_name: Optional[str] = None, avatar: Optional[str] = None) -> AgentMessage`.
  4. Define `project_member_turn_to_room(member_messages: List[AgentMessage], room_session_id: str, speaker_role: str, speaker_name: Optional[str] = None, avatar: Optional[str] = None) -> List[AgentMessage]`.
  5. Define `TeamThreadProjection` class coordinating member sessions and projected messages in `SessionStore`.

### Task 3: Export in `atbmind_core/roles/__init__.py`
- **File**: `atbmind_core/roles/__init__.py`
- **Steps**:
  1. Export `derive_member_session_id`, `parse_member_session_id`, `tag_message_speaker`, `project_member_turn_to_room`, `TeamThreadProjection`.

### Task 4: Verify test suite and zero regression
- **Verification Command**:
  `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/`
  Confirm all tests pass.

### Task 5: Audit with grill-me and hand off to code review
- **Steps**:
  1. Verify edge cases (empty message lists, missing metadata, null names).
  2. Transition to `reviewing` and trigger `atb-github-code-reviewer`.
