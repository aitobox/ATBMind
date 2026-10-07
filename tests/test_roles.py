from pathlib import Path
from atbmind_core.roles.loader import RoleLoader
from atbmind_core.roles.registry import RoleRegistry
from atbmind_core.skills.schema import Skill, SkillMetadata

def test_load_role_and_build_system_prompt(tmp_path: Path):
    role_dir = tmp_path / "test_role"
    role_dir.mkdir()
    role_yaml = role_dir / "role.yaml"
    role_yaml.write_text(
        "role_id: test_role\n"
        "name: 测试专家\n"
        "description: 测试描述\n"
        "personality: 幽默风趣\n"
        "system_prompt: 你是测试助手\n"
        "skills:\n  - mock_skill\n"
        "model: gpt-4o\n"
        "temperature: 0.5\n",
        encoding="utf-8"
    )

    role = RoleLoader.load_from_dir(role_dir)
    assert role.role_id == "test_role"
    assert role.name == "测试专家"
    assert role.model == "gpt-4o"
    assert role.temperature == 0.5

    mock_skill = Skill(
        metadata=SkillMetadata(name="mock_skill", description="desc"),
        domain_prompt="请按照测试规范行事",
        tools=[],
        skill_dir=str(tmp_path)
    )
    prompt = role.build_system_prompt({"mock_skill": mock_skill})
    assert "幽默风趣" in prompt
    assert "请按照测试规范行事" in prompt

def test_role_registry_scan_and_get(tmp_path: Path):
    role_dir = tmp_path / "r1"
    role_dir.mkdir()
    (role_dir / "role.yaml").write_text(
        "role_id: r1\nname: Role One\ndescription: Desc\nsystem_prompt: Hi\n",
        encoding="utf-8"
    )

    reg = RoleRegistry()
    count = reg.scan_directory(tmp_path)
    assert count == 1
    assert "r1" in reg.list_roles()
    r = reg.get_role("r1")
    assert r.name == "Role One"
