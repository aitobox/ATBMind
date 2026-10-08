import asyncio
import io
import json
import zipfile
from pathlib import Path
import pytest

from atbmind_core.skills import (
    Skill,
    SkillLoader,
    SkillManager,
    SkillMetadata,
    SkillRegistry,
    SkillSourceInfo,
)


def test_schema_and_source_info():
    source = SkillSourceInfo(
        source_type="github",
        repo_url="https://github.com/aitobox/skills",
        branch="main",
        subpath="skills/calculator",
        installed_commit="abc1234",
        installed_at=1700000000.0,
        has_update=False,
    )
    dumped = source.model_dump()
    assert dumped["source_type"] == "github"
    assert dumped["branch"] == "main"
    reloaded = SkillSourceInfo(**dumped)
    assert reloaded.repo_url == "https://github.com/aitobox/skills"

    meta = SkillMetadata(
        name="test_skill",
        description="A test skill",
        version="1.2.0",
        tags=["math", "utility"],
        author="Alice",
        repository="https://github.com/test/repo",
        enabled=True,
        bound_roles=["draw_expert"],
    )
    assert meta.author == "Alice"
    assert "draw_expert" in meta.bound_roles


def test_loader_with_source_json_and_extended_meta(tmp_path: Path):
    skill_dir = tmp_path / "extended_skill"
    skill_dir.mkdir()

    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: extended_skill\n"
        "description: Extended Metadata Skill\n"
        "version: 2.0.0\n"
        "tags: ['core', 'sys']\n"
        "author: Bob\n"
        "repository: https://github.com/bob/repo\n"
        "enabled: false\n"
        "bound_roles: ['coordinator', 'draw_expert']\n"
        "---\n"
        "# Operational Rules\n"
        "Always execute safely.\n",
        encoding="utf-8",
    )

    source_data = {
        "source_type": "local",
        "installed_at": 1728340000.0,
        "is_dirty": False,
    }
    (skill_dir / ".source.json").write_text(json.dumps(source_data), encoding="utf-8")

    skill = SkillLoader.load_from_dir(skill_dir, scope="project")
    assert skill.metadata.name == "extended_skill"
    assert skill.metadata.version == "2.0.0"
    assert skill.metadata.author == "Bob"
    assert skill.metadata.repository == "https://github.com/bob/repo"
    assert skill.metadata.enabled is False
    assert skill.metadata.bound_roles == ["coordinator", "draw_expert"]
    assert skill.source is not None
    assert skill.source.source_type == "local"
    assert skill.scope == "project"


def test_manager_dual_tier_discovery(tmp_path: Path):
    proj_dir = tmp_path / "project_skills"
    glob_dir = tmp_path / "global_skills"
    proj_dir.mkdir()
    glob_dir.mkdir()

    # Skill 1 in global
    g_skill = glob_dir / "glob_skill"
    g_skill.mkdir()
    (g_skill / "SKILL.md").write_text("---\nname: glob_skill\n---\nPrompt", encoding="utf-8")

    # Skill 2 in project
    p_skill = proj_dir / "proj_skill"
    p_skill.mkdir()
    (p_skill / "SKILL.md").write_text("---\nname: proj_skill\n---\nPrompt", encoding="utf-8")

    # Conflicting skill in both: project should override global
    g_conflict = glob_dir / "shared_skill"
    g_conflict.mkdir()
    (g_conflict / "SKILL.md").write_text("---\nname: shared_skill\ndescription: From Global\n---\n", encoding="utf-8")

    p_conflict = proj_dir / "shared_skill"
    p_conflict.mkdir()
    (p_conflict / "SKILL.md").write_text("---\nname: shared_skill\ndescription: From Project\n---\n", encoding="utf-8")

    custom_reg = SkillRegistry()
    manager = SkillManager(project_dir=proj_dir, global_dir=glob_dir, registry=custom_reg)

    discovered = manager.discover_all()
    assert "glob_skill" in discovered
    assert "proj_skill" in discovered
    assert "shared_skill" in discovered
    assert discovered["glob_skill"].scope == "global"
    assert discovered["proj_skill"].scope == "project"
    # Project overrides global
    assert discovered["shared_skill"].scope == "project"
    assert discovered["shared_skill"].metadata.description == "From Project"


def test_manager_import_from_local_directory(tmp_path: Path):
    source_dir = tmp_path / "my_source_skill"
    source_dir.mkdir()
    (source_dir / "SKILL.md").write_text(
        "---\nname: imported_alpha\ndescription: Imported Alpha\ntags: ['a']\n---\n# Alpha body",
        encoding="utf-8",
    )

    proj_dir = tmp_path / "proj"
    glob_dir = tmp_path / "glob"
    custom_reg = SkillRegistry()
    manager = SkillManager(project_dir=proj_dir, global_dir=glob_dir, registry=custom_reg)

    skill = manager.import_from_local(source_dir, target_scope="global")
    assert skill.metadata.name == "imported_alpha"
    assert skill.scope == "global"
    assert skill.source.source_type == "local"
    assert (glob_dir / "imported_alpha" / ".source.json").exists()
    assert custom_reg.get_skill("imported_alpha") is not None

    # Error without overwrite
    with pytest.raises(FileExistsError):
        manager.import_from_local(source_dir, target_scope="global", overwrite=False)

    # Success with overwrite
    skill2 = manager.import_from_local(source_dir, target_scope="global", overwrite=True)
    assert skill2.metadata.name == "imported_alpha"


def test_manager_import_from_local_zip_with_unwrapping(tmp_path: Path):
    zip_path = tmp_path / "archive.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(
            "root_container/SKILL.md",
            "---\nname: zipped_skill\ndescription: From Zip\n---\n# Zip Guide",
        )
        zf.writestr(
            "root_container/extra.txt",
            "extra data",
        )

    proj_dir = tmp_path / "proj"
    glob_dir = tmp_path / "glob"
    custom_reg = SkillRegistry()
    manager = SkillManager(project_dir=proj_dir, global_dir=glob_dir, registry=custom_reg)

    skill = manager.import_from_local(zip_path, target_scope="project")
    assert skill.metadata.name == "zipped_skill"
    assert skill.scope == "project"
    assert (proj_dir / "zipped_skill" / "extra.txt").exists()
    assert (proj_dir / "zipped_skill" / ".source.json").exists()


def test_manager_zip_slip_security_defense(tmp_path: Path):
    """Verify that path traversal in ZIP archives triggers a security error."""
    bad_zip_path = tmp_path / "evil.zip"
    with zipfile.ZipFile(bad_zip_path, "w") as zf:
        zf.writestr("../evil_escape.txt", "Malicious file escaping destination")
        zf.writestr("SKILL.md", "---\nname: evil\n---\n")

    proj_dir = tmp_path / "proj"
    glob_dir = tmp_path / "glob"
    manager = SkillManager(project_dir=proj_dir, global_dir=glob_dir)

    with pytest.raises(ValueError, match="Zip Slip"):
        manager.import_from_local(bad_zip_path, target_scope="global")

    # Confirm the evil file was never created outside
    assert not (tmp_path / "evil_escape.txt").exists()


@pytest.mark.asyncio
async def test_manager_create_skill_scaffolding(tmp_path: Path):
    proj_dir = tmp_path / "proj"
    glob_dir = tmp_path / "glob"
    custom_reg = SkillRegistry()
    manager = SkillManager(project_dir=proj_dir, global_dir=glob_dir, registry=custom_reg)

    skill = manager.create_skill(
        name="web_researcher",
        description="Searches web articles",
        tags=["web", "search"],
        with_tools=True,
        target_scope="global",
        author="Developer",
    )

    assert skill.metadata.name == "web_researcher"
    assert skill.metadata.author == "Developer"
    assert skill.metadata.tags == ["web", "search"]
    assert skill.source.source_type == "scaffold"
    assert len(skill.tools) == 1

    tool = skill.tools[0]
    assert tool.name == "web_researcher_action"

    # Test executing the generated tool
    input_cls = tool.parameters_schema
    tool_input = input_cls(query="quantum computing")
    result = await tool.execute(tool_input)
    assert not result.is_error
    assert "quantum computing" in result.output

    # Test get_skill and remove_skill
    assert manager.get_skill("web_researcher") is not None
    removed = manager.remove_skill("web_researcher", scope="global")
    assert removed is True
    assert manager.get_skill("web_researcher") is None
    assert not (glob_dir / "web_researcher").exists()


def test_manager_create_skill_without_tools(tmp_path: Path):
    proj_dir = tmp_path / "proj"
    glob_dir = tmp_path / "glob"
    custom_reg = SkillRegistry()
    manager = SkillManager(project_dir=proj_dir, global_dir=glob_dir, registry=custom_reg)

    skill = manager.create_skill(
        name="prompt_only_skill",
        description="Guidance without python tools",
        with_tools=False,
        target_scope="project",
    )

    assert skill.metadata.name == "prompt_only_skill"
    assert len(skill.tools) == 0
    assert not (proj_dir / "prompt_only_skill" / "tools.py").exists()
    assert (proj_dir / "prompt_only_skill" / "SKILL.md").exists()


def test_set_skill_enabled_injects_field_if_missing(tmp_path: Path):
    proj_dir = tmp_path / "proj"
    proj_dir.mkdir(parents=True, exist_ok=True)
    skill_dir = proj_dir / "no_enabled_skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: no_enabled_skill\ndescription: Test\nversion: 1.0.0\n---\n\nSkill guidelines here.\n",
        encoding="utf-8",
    )
    custom_reg = SkillRegistry()
    manager = SkillManager(project_dir=proj_dir, registry=custom_reg)
    manager.discover_all()

    res = manager.set_skill_enabled("no_enabled_skill", False)
    assert res is True
    skill = manager.get_skill("no_enabled_skill")
    assert skill is not None
    assert skill.metadata.enabled is False
    content = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    assert "enabled: false" in content

    res = manager.set_skill_enabled("no_enabled_skill", True)
    assert res is True
    skill = manager.get_skill("no_enabled_skill")
    assert skill is not None
    assert skill.metadata.enabled is True
    content = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    assert "enabled: true" in content
