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


def test_robot_role_excludes_disabled_skills(tmp_path: Path):
    from atbmind_core.roles.schema import RobotRole
    from atbmind_core.harness.tools.base import AgentTool, ToolResult
    from pydantic import BaseModel

    class DummyParams(BaseModel):
        x: str

    class DummyTool(AgentTool):
        name: str = "dummy_tool"
        description: str = "A dummy tool"
        parameters_schema: type[BaseModel] = DummyParams

        async def execute(self, params: DummyParams) -> ToolResult:
            return ToolResult(output="ok")

    class DisabledTool(AgentTool):
        name: str = "disabled_tool"
        description: str = "A disabled tool"
        parameters_schema: type[BaseModel] = DummyParams

        async def execute(self, params: DummyParams) -> ToolResult:
            return ToolResult(output="ok")

    role = RobotRole(
        role_id="tester",
        name="Tester",
        description="test",
        skills=["active_skill", "disabled_skill"],
    )

    active_skill = Skill(
        metadata=SkillMetadata(name="active_skill", description="desc", enabled=True),
        domain_prompt="ACTIVE_GUIDELINES",
        tools=[DummyTool()],
        skill_dir=str(tmp_path),
    )
    disabled_skill = Skill(
        metadata=SkillMetadata(name="disabled_skill", description="desc", enabled=False),
        domain_prompt="DISABLED_GUIDELINES",
        tools=[DisabledTool()],
        skill_dir=str(tmp_path),
    )

    loaded_skills = {
        "active_skill": active_skill,
        "disabled_skill": disabled_skill,
    }

    prompt = role.build_system_prompt(loaded_skills)
    assert "ACTIVE_GUIDELINES" in prompt
    assert "DISABLED_GUIDELINES" not in prompt

    tools = role.collect_tools(loaded_skills)
    tool_names = [t.name for t in tools]
    assert "dummy_tool" in tool_names
    assert "disabled_tool" not in tool_names
