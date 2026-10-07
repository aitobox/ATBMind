"""
ATBMind Storage Data Schemas
Defines SessionRecord and MessageRecord models for persistence.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SessionRecord(BaseModel):
    """
    Persistent metadata record for an ATBMind multi-turn conversation session.
    Stored in the 'sessions' table of data/atbmind.db.
    """

    session_id: str = Field(..., description="Unique UUID for this session")
    title: str = Field(default="新对话", description="Human-readable session title")
    workspace_name: str = Field(default="ATBMind", description="Workspace name / repository context")
    is_pinned: bool = Field(default=False, description="Whether the session is pinned to top")
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


class TemplateMetadata(BaseModel):
    """
    Standard metadata definition for domain instruction/prompt templates.
    Used for local SQLite indexing and retrieval.
    """

    template_id: str = Field(..., description="Unique identifier for the template, e.g. T_DRAW_0102")
    name: str = Field(..., description="Human-readable name of the template")
    category: str = Field(..., description="Domain category, e.g. body_shaping, face_sculpting, skin_lighting")
    keywords: List[str] = Field(default_factory=list, description="Searchable keyword tags")
    target_scope: str = Field(..., description="Target object scope: single_person, background, mesh, etc.")
    slot_definitions: Dict[str, Any] = Field(
        default_factory=dict,
        description="Definitions of configurable slots/parameters including type and default value",
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="List of template_ids that must precede this template",
    )


class WorkflowExecutionReport(BaseModel):
    """Execution report model for generated artifacts and pipeline summaries."""

    request_id: str = Field(default_factory=lambda: uuid.uuid4().hex, description="Traceable request ID")
    plugin_id: str = Field(default="draw", description="Target role or plugin identifier")
    success: bool = Field(default=True, description="Whether overall workflow succeeded")
    total_execution_time_ms: float = Field(default=0.0, description="Total duration in ms")
    final_output: Dict[str, Any] = Field(default_factory=dict, description="Output payload containing image_path etc.")
    executed_steps: List[Any] = Field(default_factory=list, description="Executed step records")
    step_results: List[Any] = Field(default_factory=list, description="Step result objects")


