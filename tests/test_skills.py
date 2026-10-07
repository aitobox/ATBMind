from pathlib import Path
from atbmind_core.skills.loader import SkillLoader
from atbmind_core.skills.registry import SkillRegistry

def test_load_skill_from_markdown(tmp_path: Path):
    skill_dir = tmp_path / "mock_skill"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        "---\n"
        "name: mock_skill\n"
        "description: Mock Description\n"
        "version: 1.0.0\n"
        "tags: ['test', 'mock']\n"
        "---\n"
        "# Rules\n"
        "Always return mock results.\n",
        encoding="utf-8"
    )
    tools_py = skill_dir / "tools.py"
    tools_py.write_text(
        "from atbmind_core.harness.tools.base import AgentTool, ToolResult\n"
        "from pydantic import BaseModel\n"
        "class MockInput(BaseModel):\n    arg: str = ''\n"
        "class MockTool(AgentTool):\n"
        "    name = 'mock_tool'\n"
        "    description = 'mock tool description'\n"
        "    parameters_schema = MockInput\n"
        "    async def execute(self, args, ctx=None): return ToolResult('ok')\n",
        encoding="utf-8"
    )

    skill = SkillLoader.load_from_dir(skill_dir)
    assert skill.metadata.name == "mock_skill"
    assert skill.metadata.description == "Mock Description"
    assert skill.metadata.version == "1.0.0"
    assert skill.metadata.tags == ["test", "mock"]
    assert "Always return mock results." in skill.domain_prompt
    assert len(skill.tools) == 1
    assert skill.tools[0].name == "mock_tool"

def test_skill_registry_scan_and_get(tmp_path: Path):
    skill_dir = tmp_path / "calc_skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: calc_skill\ndescription: Calculator\n---\nCalculate values.",
        encoding="utf-8"
    )

    reg = SkillRegistry()
    count = reg.scan_directory(tmp_path)
    assert count == 1
    assert "calc_skill" in reg.list_skills()
    s = reg.get_skill("calc_skill")
    assert s.metadata.name == "calc_skill"
