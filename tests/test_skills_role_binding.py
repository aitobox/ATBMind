import json
from pathlib import Path
import pytest
import yaml

from atbmind_core.roles import RoleRegistry, RobotRole
from atbmind_core.skills import SkillManager, SkillRegistry


def test_bind_and_unbind_skill_to_role(tmp_path: Path):
    roles_dir = tmp_path / "roles"
    roles_dir.mkdir()
    role_dir = roles_dir / "draw_expert"
    role_dir.mkdir()

    initial_yaml = {
        "role_id": "draw_expert",
        "name": "视觉专家",
        "description": "图像处理专家",
        "personality": "严谨精细",
        "system_prompt": "负责高质量图像处理",
        "skills": ["image_generation"],
        "model": "gpt-4o",
    }
    (role_dir / "role.yaml").write_text(yaml.safe_dump(initial_yaml), encoding="utf-8")

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    role_reg = RoleRegistry()
    role_reg.scan_directory(roles_dir)
    skill_reg = SkillRegistry()

    manager = SkillManager(
        project_dir=skills_dir,
        roles_dir=roles_dir,
        registry=skill_reg,
        role_registry=role_reg,
    )

    # 1. Create a skill
    skill = manager.create_skill(
        name="sketch_master",
        description="专业线稿素描生成指南",
        with_tools=True,
        target_scope="project",
    )
    assert skill.metadata.name == "sketch_master"

    # 2. Bind skill to role
    res = manager.bind_skill_to_role("draw_expert", "sketch_master")
    assert res is True

    # Verify YAML updated on disk
    updated_yaml = yaml.safe_load((role_dir / "role.yaml").read_text(encoding="utf-8"))
    assert "sketch_master" in updated_yaml["skills"]
    assert "image_generation" in updated_yaml["skills"]

    # Verify role in memory was hot-reloaded
    reloaded_role = role_reg.get_role("draw_expert")
    assert "sketch_master" in reloaded_role.skills

    # Verify system prompt composition includes domain guidelines from sketch_master
    all_skills = manager.discover_all()
    prompt = reloaded_role.build_system_prompt(all_skills)
    assert "sketch_master" in prompt
    assert "专业线稿素描生成指南" in prompt

    # Verify tool collection includes sketch_master tool
    tools = reloaded_role.collect_tools(all_skills)
    tool_names = [t.name for t in tools]
    assert "sketch_master_action" in tool_names

    # 3. Unbind skill from role
    res_unbind = manager.unbind_skill_from_role("draw_expert", "sketch_master")
    assert res_unbind is True

    unbound_yaml = yaml.safe_load((role_dir / "role.yaml").read_text(encoding="utf-8"))
    assert "sketch_master" not in unbound_yaml["skills"]

    reloaded_role_after = role_reg.get_role("draw_expert")
    assert "sketch_master" not in reloaded_role_after.skills


def test_check_requirements_present_and_missing(tmp_path: Path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    manager = SkillManager(project_dir=skills_dir, registry=SkillRegistry())

    skill = manager.create_skill(
        name="dep_checker",
        description="Skill with deps",
        with_tools=False,
        target_scope="project",
    )

    # Skill without requirements.txt
    res_empty = manager.check_requirements("dep_checker")
    assert res_empty["has_requirements"] is False
    assert res_empty["missing"] == []

    # Add requirements.txt with 1 existing package and 1 nonexistent package
    req_file = Path(skill.skill_dir) / "requirements.txt"
    req_file.write_text("pydantic>=2.0.0\nnonexistent_fictional_pkg_404>=1.0\n# comment line\n", encoding="utf-8")

    res = manager.check_requirements("dep_checker")
    assert res["has_requirements"] is True
    assert any("pydantic" in p for p in res["satisfied"])
    assert any("nonexistent_fictional_pkg_404" in p for p in res["missing"])
