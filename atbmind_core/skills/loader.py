"""
ATBMind Skill Loader
Parses SKILL.md (YAML frontmatter + Markdown body) and dynamically imports AgentTools from tools.py.
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import logging
import re
from pathlib import Path
from typing import List, Literal, Optional
import yaml

from atbmind_core.harness.tools.base import AgentTool
from atbmind_core.skills.schema import Skill, SkillMetadata, SkillSourceInfo

logger = logging.getLogger("atbmind.skills.loader")

FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


class SkillLoader:
    """Utility to load a Skill package from a directory."""

    @classmethod
    def load_from_dir(cls, skill_dir: Path | str, scope: Optional[Literal["project", "global"]] = None) -> Skill:
        path = Path(skill_dir).resolve()
        if not path.is_dir():
            raise ValueError(f"Skill path is not a directory: {path}")

        skill_md_path = path / "SKILL.md"
        meta_dict = {}
        domain_prompt = ""

        if skill_md_path.exists():
            content = skill_md_path.read_text(encoding="utf-8")
            match = FRONTMATTER_PATTERN.match(content)
            if match:
                yaml_text = match.group(1)
                domain_prompt = match.group(2).strip()
                try:
                    loaded = yaml.safe_load(yaml_text)
                    if isinstance(loaded, dict):
                        meta_dict = loaded
                except Exception as e:
                    logger.warning("Failed parsing YAML frontmatter in %s: %s", skill_md_path, e)
            else:
                domain_prompt = content.strip()

        if not meta_dict.get("name"):
            meta_dict["name"] = path.name

        metadata = SkillMetadata(
            name=str(meta_dict.get("name", path.name)),
            description=str(meta_dict.get("description", "")),
            version=str(meta_dict.get("version", "1.0.0")),
            tags=list(meta_dict.get("tags") or []),
            author=meta_dict.get("author"),
            repository=meta_dict.get("repository"),
            enabled=bool(meta_dict.get("enabled", True)),
            bound_roles=list(meta_dict.get("bound_roles") or []),
        )

        # Source information from .source.json if present
        source_info: Optional[SkillSourceInfo] = None
        source_json_path = path / ".source.json"
        if source_json_path.exists():
            try:
                raw_source = json.loads(source_json_path.read_text(encoding="utf-8"))
                source_info = SkillSourceInfo(**raw_source)
            except Exception as e:
                logger.warning("Failed parsing .source.json in %s: %s", source_json_path, e)

        if source_info is None:
            # Infer default source info based on path
            is_global_path = ".atbmind" in str(path)
            source_info = SkillSourceInfo(
                source_type="local" if is_global_path else "builtin",
                installed_at=source_json_path.stat().st_mtime if source_json_path.exists() else None,
            )

        resolved_scope: Literal["project", "global"] = scope or (
            "global" if (".atbmind" in str(path)) else "project"
        )

        tools: List[AgentTool] = []
        tools_path = path / "tools.py"
        if tools_path.exists():
            tools = cls._load_tools_from_file(tools_path)

        return Skill(
            metadata=metadata,
            domain_prompt=domain_prompt,
            tools=tools,
            skill_dir=str(path),
            source=source_info,
            scope=resolved_scope,
        )

    @classmethod
    def _load_tools_from_file(cls, file_path: Path) -> List[AgentTool]:
        module_name = f"skill_tools_{file_path.parent.name}_{abs(hash(str(file_path)))}"
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            logger.warning("Unable to create module spec for %s", file_path)
            return []

        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            logger.exception("Failed executing tools module %s: %s", file_path, e)
            return []

        tools: List[AgentTool] = []
        for name, obj in inspect.getmembers(module):
            if inspect.isclass(obj) and issubclass(obj, AgentTool) and obj is not AgentTool:
                try:
                    instance = obj()
                    tools.append(instance)
                except Exception as e:
                    logger.warning("Failed instantiating tool class %s: %s", name, e)
        return tools
