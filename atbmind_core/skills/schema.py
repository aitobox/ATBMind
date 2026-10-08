"""
ATBMind Skill Schema
Defines SkillSourceInfo, SkillMetadata, and Skill model.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

from atbmind_core.harness.tools.base import AgentTool


class SkillSourceInfo(BaseModel):
    """Metadata describing the origin, upstream version, and update status of a skill."""

    source_type: Literal["github", "local", "scaffold", "builtin"] = "builtin"
    repo_url: Optional[str] = None
    branch: Optional[str] = "main"
    subpath: Optional[str] = None
    installed_commit: Optional[str] = None
    installed_at: Optional[float] = None
    latest_upstream_commit: Optional[str] = None
    has_update: bool = False
    is_dirty: bool = False


class SkillMetadata(BaseModel):
    """Metadata extracted from the YAML frontmatter of SKILL.md."""

    name: str = Field(..., description="Unique skill name identifier")
    description: str = Field(default="", description="Human-readable skill description")
    version: str = Field(default="1.0.0", description="Semver version of the skill")
    tags: List[str] = Field(default_factory=list, description="Skill categorization tags")
    author: Optional[str] = Field(default=None, description="Author or maintainer name")
    repository: Optional[str] = Field(default=None, description="Source repository URL")
    enabled: bool = Field(default=True, description="Whether the skill is actively enabled")
    bound_roles: List[str] = Field(default_factory=list, description="List of role_ids binding this skill")


class Skill(BaseModel):
    """
    Modular skill package comprising metadata, domain guidelines (prompt),
    executable AgentTool instances, directory path, and source tracking info.
    """

    model_config = {"arbitrary_types_allowed": True}

    metadata: SkillMetadata
    domain_prompt: str = Field(default="", description="Domain rules and LLM instructions from SKILL.md body")
    tools: List[AgentTool] = Field(default_factory=list, description="AgentTool instances loaded from tools.py")
    skill_dir: str = Field(..., description="Absolute path to the skill directory")
    source: Optional[SkillSourceInfo] = Field(default=None, description="Upstream source and version tracking info")
    scope: Literal["project", "global"] = Field(default="project", description="Storage scope (project-level or global user library)")
