"""
ATBMind Skill Manager Service Core
Coordinates dual-tier storage (project vs. global), local and archive imports,
safe scaffolding, version tracking (.source.json), and registration.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Dict, List, Literal, Optional

from atbmind_core.skills.loader import SkillLoader
from atbmind_core.skills.registry import SkillRegistry, get_skill_registry
from atbmind_core.skills.schema import Skill, SkillMetadata, SkillSourceInfo

logger = logging.getLogger("atbmind.skills.manager")


def _sanitize_name_to_class(name: str) -> str:
    """Convert snake_case or kebab-case name to PascalCase for tool classes."""
    clean = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    parts = [p.capitalize() for p in clean.split("_") if p]
    return "".join(parts) or "SkillCustom"


class SkillManager:
    """
    Central facade service managing the lifecycle of Skills in ATBMind:
    - Dual-tier storage: Project workspace (`skills/`) & User global library (`~/.atbmind/skills/`)
    - Local directory and ZIP archive safe import (with anti-Zip Slip traversal guards)
    - Standard scaffolding template generation (SKILL.md + tools.py + .source.json)
    - In-memory registry discovery and synchronization
    """

    def __init__(
        self,
        project_dir: Optional[Path | str] = None,
        global_dir: Optional[Path | str] = None,
        registry: Optional[SkillRegistry] = None,
    ) -> None:
        self.project_skills_dir = (
            Path(project_dir).resolve() if project_dir else (Path.cwd() / "skills").resolve()
        )
        self.global_skills_dir = (
            Path(global_dir).resolve()
            if global_dir
            else Path(os.path.expanduser("~/.atbmind/skills")).resolve()
        )
        self.registry = registry or get_skill_registry()

    def get_skills_dir(self, scope: Literal["project", "global"] = "global") -> Path:
        """Return and ensure directory for the requested scope."""
        target = self.global_skills_dir if scope == "global" else self.project_skills_dir
        target.mkdir(parents=True, exist_ok=True)
        return target

    def discover_all(self) -> Dict[str, Skill]:
        """
        Scan both project and global directories, register discovered skills,
        and return a mapping of skill_name -> Skill.
        Project-level skills take precedence over global ones with matching names.
        """
        discovered: Dict[str, Skill] = {}

        # 1. Scan global skills first
        if self.global_skills_dir.is_dir():
            for item in self.global_skills_dir.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    if (item / "SKILL.md").exists() or (item / "tools.py").exists():
                        try:
                            skill = SkillLoader.load_from_dir(item, scope="global")
                            self.registry.register_skill(skill)
                            discovered[skill.metadata.name] = skill
                        except Exception as e:
                            logger.warning("Failed loading global skill %s: %s", item, e)

        # 2. Scan project skills (overrides global if same name)
        if self.project_skills_dir.is_dir():
            for item in self.project_skills_dir.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    if (item / "SKILL.md").exists() or (item / "tools.py").exists():
                        try:
                            skill = SkillLoader.load_from_dir(item, scope="project")
                            self.registry.register_skill(skill)
                            discovered[skill.metadata.name] = skill
                        except Exception as e:
                            logger.warning("Failed loading project skill %s: %s", item, e)

        return discovered

    def list_skills(self) -> List[str]:
        """List all registered skill names."""
        return sorted(list(self.registry.list_skills()))

    def get_skill(self, name: str) -> Optional[Skill]:
        """Retrieve a skill by name from the registry or scan on demand."""
        skill = self.registry.get_skill(name)
        if skill:
            return skill
        # Try finding in project then global dir
        for scope_dir, scope in [(self.project_skills_dir, "project"), (self.global_skills_dir, "global")]:
            candidate = scope_dir / name
            if candidate.is_dir() and ((candidate / "SKILL.md").exists() or (candidate / "tools.py").exists()):
                loaded = SkillLoader.load_from_dir(candidate, scope=scope)
                self.registry.register_skill(loaded)
                return loaded
        return None

    def get_skill_path(self, name: str, scope: Optional[Literal["project", "global"]] = None) -> Optional[Path]:
        """Get the filesystem path of a skill."""
        scopes = [scope] if scope else ["project", "global"]
        for s in scopes:
            d = self.get_skills_dir(s) / name
            if d.is_dir():
                return d
        return None

    def import_from_local(
        self,
        source_path: Path | str,
        target_scope: Literal["project", "global"] = "global",
        skill_name: Optional[str] = None,
        overwrite: bool = False,
    ) -> Skill:
        """
        Import a skill from a local directory or .zip file.
        Includes strict Zip Slip directory traversal defense.
        """
        src = Path(source_path).resolve()
        if not src.exists():
            raise FileNotFoundError(f"Source path does not exist: {src}")

        target_base = self.get_skills_dir(target_scope)

        with tempfile.TemporaryDirectory() as tmp_work_dir:
            tmp_path = Path(tmp_work_dir)
            import_source_dir: Path

            if src.is_file() and src.suffix.lower() == ".zip":
                # Safe ZIP extraction with Zip Slip defense
                extract_root = tmp_path / "extracted"
                extract_root.mkdir()
                with zipfile.ZipFile(src, "r") as zf:
                    for member in zf.infolist():
                        # Validate path does not escape extract_root
                        target_member_path = (extract_root / member.filename).resolve()
                        if not target_member_path.is_relative_to(extract_root.resolve()):
                            raise ValueError(
                                f"Zip Slip vulnerability detected: '{member.filename}' escapes target extraction root."
                            )
                    zf.extractall(extract_root)

                # Single root directory penetration check
                entries = [e for e in extract_root.iterdir() if not e.name.startswith((".", "__MACOSX"))]
                if len(entries) == 1 and entries[0].is_dir():
                    import_source_dir = entries[0]
                else:
                    import_source_dir = extract_root
            elif src.is_dir():
                import_source_dir = src
            else:
                raise ValueError(f"Source must be a directory or .zip archive, got: {src}")

            # Determine target skill name
            resolved_name = skill_name
            if not resolved_name:
                skill_md = import_source_dir / "SKILL.md"
                if skill_md.exists():
                    try:
                        temp_skill = SkillLoader.load_from_dir(import_source_dir)
                        resolved_name = temp_skill.metadata.name
                    except Exception:
                        pass
            if not resolved_name:
                resolved_name = src.stem if src.is_file() else src.name

            # Target installation path
            dest_dir = target_base / resolved_name
            if dest_dir.exists():
                if not overwrite:
                    raise FileExistsError(
                        f"Skill '{resolved_name}' already exists at {dest_dir}. Use overwrite=True to replace."
                    )
                shutil.rmtree(dest_dir)

            dest_dir.mkdir(parents=True, exist_ok=True)

            # Copy all files from import_source_dir to dest_dir
            for item in import_source_dir.iterdir():
                if item.name in (".git", "__pycache__", ".DS_Store"):
                    continue
                dest_item = dest_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, dest_item, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest_item)

            # Ensure minimal SKILL.md exists if missing
            target_skill_md = dest_dir / "SKILL.md"
            if not target_skill_md.exists():
                target_skill_md.write_text(
                    f"---\nname: {resolved_name}\ndescription: Imported local skill\nversion: 1.0.0\ntags: ['local']\n---\n"
                    f"# {resolved_name}\n\nLocal imported skill instructions.\n",
                    encoding="utf-8",
                )

            # Write .source.json tracking
            source_info = SkillSourceInfo(
                source_type="local",
                installed_at=time.time(),
                is_dirty=False,
            )
            (dest_dir / ".source.json").write_text(
                json.dumps(source_info.model_dump(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            # Load and register
            skill = SkillLoader.load_from_dir(dest_dir, scope=target_scope)
            self.registry.register_skill(skill)
            logger.info("Successfully imported skill '%s' to %s", skill.metadata.name, dest_dir)
            return skill

    def create_skill(
        self,
        name: str,
        description: str = "",
        tags: Optional[List[str]] = None,
        with_tools: bool = True,
        target_scope: Literal["project", "global"] = "global",
        overwrite: bool = False,
        author: Optional[str] = None,
    ) -> Skill:
        """
        Scaffold a new standardized skill package:
        - Generates SKILL.md with standard YAML frontmatter and domain guideline sections
        - Generates tools.py with an executable AgentTool implementation if with_tools=True
        - Writes .source.json with source_type="scaffold"
        - Automatically registers into the SkillRegistry
        """
        clean_name = re.sub(r"[^a-zA-Z0-9_\-]", "", name.strip())
        if not clean_name:
            raise ValueError(f"Invalid skill name: '{name}'")

        target_base = self.get_skills_dir(target_scope)
        dest_dir = target_base / clean_name

        if dest_dir.exists():
            if not overwrite:
                raise FileExistsError(
                    f"Skill '{clean_name}' already exists at {dest_dir}. Use overwrite=True to replace."
                )
            shutil.rmtree(dest_dir)

        dest_dir.mkdir(parents=True, exist_ok=True)

        tag_list = tags or ["custom"]
        author_val = author or "ATBMind User"

        # 1. Render SKILL.md
        tags_yaml = json.dumps(tag_list)
        skill_md_content = f"""---
name: {clean_name}
description: "{description or f'Domain guidelines for {clean_name}'}"
version: 1.0.0
tags: {tags_yaml}
author: "{author_val}"
enabled: true
bound_roles: []
---

# {clean_name}

## Overview
{description or f'Domain guidelines, workflows, and operational rules for {clean_name}.'}

## Instructions & Best Practices
- Guideline 1: Carefully check input parameters and boundary requirements.
- Guideline 2: Ensure structured responses and predictable error handling.
"""
        (dest_dir / "SKILL.md").write_text(skill_md_content, encoding="utf-8")

        # 2. Render tools.py if requested
        if with_tools:
            pascal_name = _sanitize_name_to_class(clean_name)
            tool_name = f"{clean_name.replace('-', '_')}_action"
            tools_py_content = f'''"""
Executable tools exported by skill {clean_name}.
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from atbmind_core.harness.tools.base import AgentTool, ToolResult


class {pascal_name}Input(BaseModel):
    query: str = Field(default="", description="Input parameter for {tool_name}")


class {pascal_name}Tool(AgentTool):
    name = "{tool_name}"
    description = "Action tool provided by skill {clean_name}"
    parameters_schema = {pascal_name}Input

    async def execute(self, args: Any, context: Optional[Any] = None) -> ToolResult:
        query_val = getattr(args, "query", None) if not isinstance(args, dict) else args.get("query", "")
        if query_val is None:
            query_val = str(args)
        return ToolResult(
            content=f"Executed {tool_name} successfully with query: {{query_val}}",
            is_error=False,
        )
'''
            (dest_dir / "tools.py").write_text(tools_py_content, encoding="utf-8")

        # 3. Render .source.json
        source_info = SkillSourceInfo(
            source_type="scaffold",
            installed_at=time.time(),
            has_update=False,
            is_dirty=False,
        )
        (dest_dir / ".source.json").write_text(
            json.dumps(source_info.model_dump(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # 4. Load and register
        skill = SkillLoader.load_from_dir(dest_dir, scope=target_scope)
        self.registry.register_skill(skill)
        logger.info("Scaffolded new skill '%s' at %s", clean_name, dest_dir)
        return skill

    def remove_skill(
        self, name: str, scope: Optional[Literal["project", "global"]] = None
    ) -> bool:
        """Remove a skill from disk and unregister it."""
        removed = False
        scopes = [scope] if scope else ["project", "global"]
        for s in scopes:
            target_path = self.get_skills_dir(s) / name
            if target_path.is_dir():
                shutil.rmtree(target_path)
                removed = True
                logger.info("Removed skill directory %s", target_path)

        if name in self.registry._skills:
            del self.registry._skills[name]

        return removed
