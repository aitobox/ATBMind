import pytest
from pathlib import Path
from atbmind_core.skills.registry import SkillRegistry
from atbmind_core.roles.registry import RoleRegistry
from atbmind_core.roles.team import RobotTeam

@pytest.fixture
def anyio_backend():
    return "asyncio"

def test_draw_expert_role_discovery_and_tools():
    skill_reg = SkillRegistry()
    loaded_skills = skill_reg.scan_directory(Path("skills"))
    assert loaded_skills >= 1
    assert "image_generation" in skill_reg.list_skills()

    role_reg = RoleRegistry(skill_registry=skill_reg)
    loaded_roles = role_reg.scan_directory(Path("roles"))
    assert loaded_roles >= 2
    assert "draw_expert" in role_reg.list_roles()
    assert "coordinator" in role_reg.list_roles()

    draw_role = role_reg.get_role("draw_expert")
    assert draw_role is not None
    assert "image_generation" in draw_role.skills

    tools = draw_role.collect_tools(skill_reg.get_all_skills())
    tool_names = [t.name for t in tools]
    assert "generate_image" in tool_names
    assert "refine_image" in tool_names
    assert "search_templates" in tool_names

@pytest.mark.anyio
async def test_draw_expert_tool_execution(tmp_path: Path):
    skill_reg = SkillRegistry()
    skill_reg.scan_directory(Path("skills"))
    role_reg = RoleRegistry(skill_registry=skill_reg)
    role_reg.scan_directory(Path("roles"))

    draw_role = role_reg.get_role("draw_expert")
    tools = {t.name: t for t in draw_role.collect_tools(skill_reg.get_all_skills())}

    gen_tool = tools["generate_image"]
    res = await gen_tool.execute({
        "prompt": "阳光下微笑的少女",
        "style": "portrait_photography",
        "aspect_ratio": "1:1"
    })
    assert not res.is_error
    assert "image_path" in res.metadata
    assert Path(res.metadata["image_path"]).exists()
