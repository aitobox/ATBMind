"""
ATBMind RobotRole Schema
Defines RobotRole model and prompt/tool composition methods.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from atbmind_core.harness.tools.base import AgentTool
from atbmind_core.skills.schema import Skill


class RobotRole(BaseModel):
    """
    Expert agent role definition.
    Carries personality, system prompts, skill attachments, and model parameters.
    """

    role_id: str = Field(..., description="Unique role identifier")
    name: str = Field(..., description="Display name of the expert role")
    description: str = Field(default="", description="Role responsibility description")
    personality: str = Field(default="", description="Tone and persona guidelines")
    system_prompt: str = Field(default="", description="Core instructions for the role")
    skills: List[str] = Field(default_factory=list, description="List of bound skill names")
    model: Optional[str] = Field(default=None, description="Preferred LLM model name")
    temperature: Optional[float] = Field(default=None, description="Preferred temperature")
    role_dir: Optional[str] = Field(default=None, description="Source directory path")

    def build_system_prompt(self, loaded_skills: Optional[Dict[str, Skill]] = None) -> str:
        """
        Assembles complete system prompt by combining base instructions,
        personality traits, and domain guidelines from all attached skills.
        """
        parts = []
        if self.system_prompt:
            parts.append(self.system_prompt.strip())

        if self.personality:
            parts.append(f"\n【性格与人设风格】\n{self.personality.strip()}")

        if loaded_skills:
            domain_guides = []
            for s_name in self.skills:
                skill = loaded_skills.get(s_name)
                if skill and skill.domain_prompt:
                    domain_guides.append(f"### Skill 指南 [{s_name}]\n{skill.domain_prompt.strip()}")
            if domain_guides:
                parts.append("\n【领域专业技能规范】\n" + "\n\n".join(domain_guides))

        return "\n\n".join(parts)

    def collect_tools(self, loaded_skills: Optional[Dict[str, Skill]] = None) -> List[AgentTool]:
        """Collects all executable tools from attached skills."""
        if not loaded_skills:
            return []
        tools: List[AgentTool] = []
        for s_name in self.skills:
            skill = loaded_skills.get(s_name)
            if skill and skill.tools:
                tools.extend(skill.tools)
        return tools
