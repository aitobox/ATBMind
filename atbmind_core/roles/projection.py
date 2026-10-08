"""
ATBMind Team Thread Projection & Speaker Metadata Mapping.
Isolates internal subagent multi-turn execution details in virtual sub-sessions,
tagging and projecting only key deliverables into the main team room timeline.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from atbmind_core.harness.types import AgentMessage, Role
from atbmind_core.storage.session_store import SessionStore

logger = logging.getLogger("atbmind.roles.projection")

MEMBER_SESSION_DELIMITER = ":member:"


def derive_member_session_id(room_session_id: str, role_id: str) -> str:
    """Derives a deterministic isolated sub-session ID for a specialist role within a room."""
    return f"{room_session_id}{MEMBER_SESSION_DELIMITER}{role_id}"


def parse_member_session_id(member_session_id: str) -> Optional[Tuple[str, str]]:
    """
    Extracts (room_session_id, role_id) from a derived member session ID.
    Returns None if the session ID does not conform to the member sub-session pattern.
    """
    if MEMBER_SESSION_DELIMITER not in member_session_id:
        return None
    parts = member_session_id.split(MEMBER_SESSION_DELIMITER, 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return None
    return parts[0], parts[1]


def tag_message_speaker(
    msg: AgentMessage,
    speaker_role: str,
    speaker_name: Optional[str] = None,
    avatar: Optional[str] = None,
) -> AgentMessage:
    """Enriches an AgentMessage's metadata with speaker identity attributes."""
    if msg.metadata is None:
        msg.metadata = {}
    msg.metadata["speaker_role"] = speaker_role
    if speaker_name:
        msg.metadata["speaker_name"] = speaker_name
    if avatar:
        msg.metadata["avatar"] = avatar
    return msg


def project_member_turn_to_room(
    member_messages: List[AgentMessage],
    room_session_id: str,
    speaker_role: str,
    speaker_name: Optional[str] = None,
    avatar: Optional[str] = None,
) -> List[AgentMessage]:
    """
    Filters member execution messages, projecting only final replies and UI cards to the room.
    Omits intermediate tool calling, raw system prompts, and tool return data.
    """
    projected: List[AgentMessage] = []
    member_sid = derive_member_session_id(room_session_id, speaker_role)

    # Find the last assistant message with meaningful content or UI artifacts
    for msg in reversed(member_messages):
        if msg.role == Role.ASSISTANT and (
            msg.content or msg.metadata.get("ui_artifacts") or msg.metadata.get("card")
        ):
            meta = dict(msg.metadata or {})
            meta["speaker_role"] = speaker_role
            if speaker_name:
                meta["speaker_name"] = speaker_name
            if avatar:
                meta["avatar"] = avatar
            meta["projected_from_member"] = True
            meta["origin_session_id"] = member_sid

            projected_msg = AgentMessage(
                role=Role.ASSISTANT,
                content=msg.content,
                tool_calls=None,  # Strip tool calls from projected room message
                tool_call_id=None,
                name=msg.name,
                metadata=meta,
            )
            projected.append(projected_msg)
            break

    projected.reverse()
    return projected


from atbmind_core.storage.schemas import MessageRecord, SessionRecord


class TeamThreadProjection:
    """
    Coordinates session checkpoint isolation and projected room synchronization
    backed by SessionStore.
    """

    def __init__(self, store: Optional[SessionStore] = None) -> None:
        self.store = store

    def get_or_create_member_session(
        self,
        room_session_id: str,
        role_id: str,
        title: Optional[str] = None,
    ) -> str:
        """Ensures a virtual sub-session exists for the specialist in SessionStore."""
        member_sid = derive_member_session_id(room_session_id, role_id)
        if self.store:
            existing = self.store.get_session(member_sid)
            if not existing:
                default_title = title or f"Member [{role_id}] for Room [{room_session_id}]"
                self.store.create_session(
                    SessionRecord(session_id=member_sid, title=default_title)
                )
        return member_sid

    def project_to_room(
        self,
        room_session_id: str,
        role_id: str,
        member_messages: List[AgentMessage],
        speaker_name: Optional[str] = None,
        avatar: Optional[str] = None,
    ) -> List[AgentMessage]:
        """
        Projects member messages to the room conversation and optionally persists
        them to SessionStore if available.
        """
        projected = project_member_turn_to_room(
            member_messages=member_messages,
            room_session_id=room_session_id,
            speaker_role=role_id,
            speaker_name=speaker_name,
            avatar=avatar,
        )

        if self.store:
            for p_msg in projected:
                rec = MessageRecord(
                    session_id=room_session_id,
                    role=p_msg.role.value,
                    content=p_msg.content or "",
                    plugin_payload=p_msg.metadata,
                )
                self.store.append_message(rec)

        return projected

