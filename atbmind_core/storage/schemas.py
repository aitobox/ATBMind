"""
ATBMind Storage Data Schemas
Defines SessionRecord and MessageRecord models for persistence.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class SessionRecord(BaseModel):
    """
    Persistent metadata record for an ATBMind multi-turn conversation session.
    Stored in the 'sessions' table of data/atbmind.db.
    """

    session_id: str = Field(..., description="Unique UUID for this session")
    title: str = Field(default="新对话", description="Human-readable session title")
    active_role_id: Optional[str] = Field(
        default=None,
        description="Currently active role ID, e.g. 'draw_expert'; None means coordinator",
    )
    active_plugin_id: Optional[str] = Field(
        default=None,
        description="Legacy alias for active_role_id",
    )
    plugin_state: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON-serialisable UI state: {model, aspect_ratio, style_id, template_id}",
    )
    created_at: float = Field(default_factory=time.time, description="Unix epoch timestamp of session creation")
    updated_at: float = Field(default_factory=time.time, description="Unix epoch timestamp of last modification")


class MessageRecord(BaseModel):
    """
    Single message record within a session, stored in the 'messages' table.
    Supports text, attachments, and structured payloads.
    """

    message_id: str = Field(default_factory=lambda: uuid.uuid4().hex, description="Unique UUID for this message")
    session_id: str = Field(..., description="Parent session UUID")
    role: str = Field(..., description="Message author role: 'user' | 'assistant' | 'system' | 'tool'")
    content: str = Field(default="", description="Text content of the message or assistant reply")
    attachment_path: Optional[str] = Field(
        default=None,
        description="Absolute path to user-uploaded image attachment, if any",
    )
    role_id: Optional[str] = Field(
        default=None,
        description="Role that generated this message, e.g. 'draw_expert'",
    )
    plugin_id: Optional[str] = Field(
        default=None,
        description="Legacy alias for role_id",
    )
    plugin_payload: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Structured result payload: {before_img, after_img, plan, report, elapsed_seconds}",
    )
    created_at: float = Field(default_factory=time.time, description="Unix epoch timestamp of message creation")
