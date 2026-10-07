"""
ATBMind Skill Schema
Defines SkillMetadata and Skill model.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from atbmind_core.harness.tools.base import AgentTool


class SkillMetadata(BaseModel):
    """Metadata extracted from the YAML frontmatter of SKILL.md."""

    name: str = Field(..., description="Unique skill name identifier")
    description: str = Field(default="", description="Human-readable skill description")
    version: str = Field(default="1.0.0", description="Semver version of the skill")
    tags: List[str] = Field(default_factory=list, description="Skill categorization tags")


class Skill(BaseModel):
    """
    Modular skill package comprising metadata, domain guidelines (prompt),
    executable AgentTool instances, and directory path.
    """

    model_config = {"arbitrary_types_allowed": True}

    metadata: SkillMetadata
    domain_prompt: str = Field(default="", description="Domain rules and LLM instructions from SKILL.md body")
    tools: List[AgentTool] = Field(default_factory=list, description="AgentTool instances loaded from tools.py")
    skill_dir: str = Field(..., description="Absolute path to the skill directory")
