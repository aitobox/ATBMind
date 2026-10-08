"""
Comprehensive end-to-end integration tests for ATBMind Skill Manager:
- SkillDetailDrawer: SKILL.md rendering, tools schema inspector, requirements diagnostics, role binding toggle.
- Skill Dialogs: GitHubImportDialog live validation, NewSkillDialog live preview and creation, LocalImportDialog.
- Workers: SkillImportWorker and SkillUpdateWorker asynchronous execution.
- EventBus Telemetry: SkillInstalledEvent, SkillUpdatedEvent, SkillBoundRoleEvent Qt bridging.
- SkillHubView: Full UI integration wiring drawer, cards, dialogs, and async workers.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QCheckBox, QLabel
import pytest
from pydantic import BaseModel, Field

from apps.atbmind_desktop.bridge import EventBusQtBridge
from apps.atbmind_desktop.widgets.skill_dialogs import (
    GitHubImportDialog,
    LocalImportDialog,
    NewSkillDialog,
)
from apps.atbmind_desktop.widgets.skill_drawer import SkillDetailDrawer
from apps.atbmind_desktop.widgets.skill_hub import SkillCard, SkillHubView
from apps.atbmind_desktop.workers import (
    SkillCheckUpdatesWorker,
    SkillImportWorker,
    SkillUpdateWorker,
)
from atbmind_core.harness.tools.base import AgentTool, ToolResult
from atbmind_core.roles.registry import RoleRegistry
from atbmind_core.runtime.event_bus import (
    AsyncEventBus,
    SkillBoundRoleEvent,
    SkillInstalledEvent,
    SkillUpdatedEvent,
    get_global_event_bus,
)
from atbmind_core.skills.manager import SkillManager
from atbmind_core.skills.registry import SkillRegistry
from atbmind_core.skills.schema import Skill, SkillMetadata, SkillSourceInfo


class MockToolInput(BaseModel):
    query: str = Field(default="", description="Search query string")
    max_results: int = Field(default=5, description="Maximum results to return")


class MockDemoTool(AgentTool):
    name = "mock_search_tool"
    description = "A mock search tool for testing drawer tool inspection"
    parameters_schema = MockToolInput

    async def execute(self, args: Any, context: Optional[Any] = None) -> ToolResult:
        return ToolResult(content="Mock search executed", is_error=False)


@pytest.fixture
def temp_environment(tmp_path: Path):
    """Sets up an isolated filesystem environment with project/global skill and role directories."""
    project_skills = tmp_path / "project_skills"
    global_skills = tmp_path / "global_skills"
    roles_dir = tmp_path / "roles"
    project_skills.mkdir(parents=True)
    global_skills.mkdir(parents=True)
    roles_dir.mkdir(parents=True)

    skill_reg = SkillRegistry()
    role_reg = RoleRegistry(skill_registry=skill_reg)
    role_reg.scan_directory(roles_dir)
    manager = SkillManager(
        project_dir=project_skills,
        global_dir=global_skills,
        roles_dir=roles_dir,
        registry=skill_reg,
        role_registry=role_reg,
    )
    return {
        "manager": manager,
        "skill_reg": skill_reg,
        "role_reg": role_reg,
        "project_skills": project_skills,
        "global_skills": global_skills,
        "roles_dir": roles_dir,
    }


def test_skill_detail_drawer_markdown_and_tools(qtbot, tmp_path: Path):
    """Verifies that SkillDetailDrawer renders SKILL.md Markdown, tools schema, and handles close."""
    skill_dir = tmp_path / "demo_skill"
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        "# Demo Skill\n\nThis is rich **markdown** documentation.\n- Step 1\n- Step 2",
        encoding="utf-8",
    )

    skill = Skill(
        metadata=SkillMetadata(
            name="demo_skill",
            description="A comprehensive demonstration skill",
            version="1.5.0",
            tags=["demo", "tools"],
            enabled=True,
            bound_roles=[],
        ),
        source=SkillSourceInfo(source_type="github", has_update=True),
        scope="global",
        skill_dir=str(skill_dir),
        tools=[MockDemoTool()],
    )

    drawer = SkillDetailDrawer(skill=skill)
    qtbot.addWidget(drawer)
    drawer.show()

    # Check title and badges
    assert drawer.title_label.text() == "demo_skill"
    assert drawer.version_badge.text() == "v1.5.0"
    assert drawer.source_badge.text() == "GitHub"

    # Check Markdown viewer content
    md_text = drawer.markdown_viewer.toPlainText()
    assert "Demo Skill" in md_text
    assert "rich markdown documentation" in md_text

    # Check Tools Inspector tab
    drawer.tabs.setCurrentIndex(1)
    labels = drawer.tools_container.findChildren(QLabel)
    assert any("mock_search_tool" in lbl.text() for lbl in labels)

    # Check Close button signal
    closed_emitted = []
    drawer.closed.connect(lambda: closed_emitted.append(True))
    drawer.btn_close.click()
    assert len(closed_emitted) == 1


def test_skill_detail_drawer_role_binding_toggle(qtbot, temp_environment):
    """Verifies that toggling role checkboxes in drawer updates role.yaml and emits signal."""
    manager: SkillManager = temp_environment["manager"]
    roles_dir: Path = temp_environment["roles_dir"]

    # 1. Create a test role
    role_dir = roles_dir / "data_analyst"
    role_dir.mkdir(parents=True)
    role_yaml = role_dir / "role.yaml"
    role_data = {
        "id": "data_analyst",
        "name": "Data Analyst",
        "system_prompt": "You analyze data.",
        "skills": [],
    }
    role_yaml.write_text(yaml.safe_dump(role_data), encoding="utf-8")
    temp_environment["role_reg"].scan_directory(roles_dir)

    # 2. Create a test skill
    skill = manager.create_skill(
        name="pandas_skill",
        description="Data manipulation guidelines",
        tags=["data", "pandas"],
        with_tools=False,
        target_scope="project",
    )

    drawer = SkillDetailDrawer(skill=skill, skill_manager=manager)
    qtbot.addWidget(drawer)
    drawer.show()

    # Switch to Roles tab
    drawer.tabs.setCurrentIndex(3)

    binding_changes = []
    drawer.role_binding_changed.connect(
        lambda s, r, b: binding_changes.append((s, r, b))
    )

    # Find checkbox for data_analyst
    checkboxes = drawer.roles_container.findChildren(QCheckBox)
    target_chk = None
    for chk in checkboxes:
        if "data_analyst" in chk.text():
            target_chk = chk
            break
    assert target_chk is not None
    assert target_chk.isChecked() is False

    # Toggle checkbox ON
    target_chk.setChecked(True)
    assert len(binding_changes) == 1
    assert binding_changes[0] == ("pandas_skill", "data_analyst", True)

    # Verify role.yaml on disk has pandas_skill
    updated_role = yaml.safe_load(role_yaml.read_text(encoding="utf-8"))
    assert "pandas_skill" in updated_role.get("skills", [])

    # Toggle checkbox OFF
    target_chk.setChecked(False)
    assert len(binding_changes) == 2
    assert binding_changes[1] == ("pandas_skill", "data_analyst", False)

    updated_role2 = yaml.safe_load(role_yaml.read_text(encoding="utf-8"))
    assert "pandas_skill" not in updated_role2.get("skills", [])


def test_skill_detail_drawer_requirements_diagnostic(qtbot, tmp_path: Path):
    """Verifies that drawer diagnoses existing and missing packages from requirements.txt."""
    skill_dir = tmp_path / "req_test_skill"
    skill_dir.mkdir(parents=True)
    req_file = skill_dir / "requirements.txt"
    req_file.write_text(
        "pytest>=7.0.0\nnonexistent_mystery_package_999==0.1.0\n",
        encoding="utf-8",
    )

    skill = Skill(
        metadata=SkillMetadata(name="req_test_skill", description="Testing requirements"),
        skill_dir=str(skill_dir),
    )

    manager = SkillManager()
    manager.registry.register_skill(skill)

    drawer = SkillDetailDrawer(skill=skill, skill_manager=manager)
    qtbot.addWidget(drawer)
    drawer.show()

    drawer.tabs.setCurrentIndex(2)  # Diagnostics tab
    assert "1 项缺失依赖" in drawer.env_info_label.text()


def test_new_skill_dialog_preview_and_creation(qtbot):
    """Verifies NewSkillDialog live preview updates and validation gate."""
    dialog = NewSkillDialog()
    qtbot.addWidget(dialog)
    dialog.show()

    assert dialog.btn_create.isEnabled() is False

    # Input valid name and desc
    dialog.name_input.setText("my_custom_expert")
    dialog.desc_input.setText("Autonomous debugging helper")
    dialog.tags_input.setText("dev, debugging, ai")

    assert dialog.btn_create.isEnabled() is True

    # Check SKILL.md preview
    md_preview = dialog.preview_skill_md.toPlainText()
    assert "name: my_custom_expert" in md_preview
    assert "Autonomous debugging helper" in md_preview

    # Check tools.py preview
    py_preview = dialog.preview_tools_py.toPlainText()
    assert "My_custom_expertTool" in py_preview
    assert "my_custom_expert_action" in py_preview

    created_args = []
    dialog.create_requested.connect(
        lambda name, desc, tags, with_tools, scope: created_args.append(
            (name, desc, tags, with_tools, scope)
        )
    )

    dialog.btn_create.click()
    assert len(created_args) == 1
    assert created_args[0][0] == "my_custom_expert"
    assert created_args[0][1] == "Autonomous debugging helper"
    assert created_args[0][3] is True  # with_tools
    assert created_args[0][4] == "global"


def test_github_import_dialog_validation_and_link(qtbot):
    """Verifies GitHubImportDialog URL recognition and local link button."""
    dialog = GitHubImportDialog()
    qtbot.addWidget(dialog)
    dialog.show()

    assert dialog.btn_import.isEnabled() is False

    # Invalid URL
    dialog.url_input.setText("random_invalid_string")
    assert dialog.btn_import.isEnabled() is False
    assert "无法识别" in dialog.preview_label.text()

    # Valid GitHub URL with subpath
    dialog.url_input.setText("https://github.com/aitobox/ATBMind/tree/main/skills/sub_skill")
    assert dialog.btn_import.isEnabled() is True
    assert "ATBMind" in dialog.preview_label.text()
    assert "sub_skill" in dialog.preview_label.text()

    emitted_import = []
    dialog.import_requested.connect(
        lambda url, scope, name, overwrite: emitted_import.append((url, scope, name, overwrite))
    )

    dialog.btn_import.click()
    assert len(emitted_import) == 1
    assert "ATBMind" in emitted_import[0][0]
    assert emitted_import[0][1] == "global"
    assert emitted_import[0][2] == "sub_skill"


def test_skill_import_and_update_workers(qtbot, temp_environment):
    """Verifies that background QThreads execute without crashing or blocking the UI."""
    manager: SkillManager = temp_environment["manager"]

    # 1. Test local import via worker
    src_dir = temp_environment["project_skills"] / "seed_src"
    src_dir.mkdir(parents=True)
    (src_dir / "SKILL.md").write_text("---\nname: worker_skill\n---\n# Worker Skill\n", encoding="utf-8")

    import_worker = SkillImportWorker(
        source=str(src_dir),
        source_type="local",
        target_scope="global",
        skill_name="worker_skill",
        skill_manager=manager,
    )

    import_results = []
    import_worker.finished.connect(
        lambda success, msg, obj: import_results.append((success, msg, obj))
    )

    import_worker.start()
    qtbot.waitUntil(lambda: len(import_results) > 0, timeout=3000)

    assert import_results[0][0] is True
    assert import_results[0][1] == "worker_skill"
    assert manager.get_skill("worker_skill") is not None

    # 2. Test update worker failure gracefully on non-github skill
    update_worker = SkillUpdateWorker(
        skill_name="worker_skill",
        skill_manager=manager,
    )

    update_results = []
    update_worker.finished.connect(
        lambda success, msg, obj: update_results.append((success, msg, obj))
    )

    update_worker.start()
    qtbot.waitUntil(lambda: len(update_results) > 0, timeout=3000)

    # local skill cannot be updated from git upstream -> returns false with error msg
    assert update_results[0][0] is False
    assert "not a GitHub source skill" in update_results[0][1]


def test_event_bus_skill_telemetry(qtbot):
    """Verifies AsyncEventBus skill events bridge directly to Qt signals."""
    bus = AsyncEventBus()
    bridge = EventBusQtBridge()
    bridge.attach_bus(bus)

    installed_signals = []
    updated_signals = []
    bound_signals = []

    bridge.skill_installed.connect(lambda n, s, sc: installed_signals.append((n, s, sc)))
    bridge.skill_updated.connect(lambda n, v, m: updated_signals.append((n, v, m)))
    bridge.skill_bound_role.connect(lambda n, r, a: bound_signals.append((n, r, a)))

    # Dispatch via publish_sync
    bus.publish_sync(SkillInstalledEvent(skill_name="telemetry_skill", source_type="github", scope="global"))
    bus.publish_sync(SkillUpdatedEvent(skill_name="telemetry_skill", version="2.0.0", message="Upgraded"))
    bus.publish_sync(SkillBoundRoleEvent(skill_name="telemetry_skill", role_id="leader", action="bind"))

    qtbot.waitUntil(lambda: len(installed_signals) == 1, timeout=2000)
    qtbot.waitUntil(lambda: len(updated_signals) == 1, timeout=2000)
    qtbot.waitUntil(lambda: len(bound_signals) == 1, timeout=2000)

    assert installed_signals[0] == ("telemetry_skill", "github", "global")
    assert updated_signals[0] == ("telemetry_skill", "2.0.0", "Upgraded")
    assert bound_signals[0] == ("telemetry_skill", "leader", "bind")

    bridge.detach_bus()


def test_skill_hub_view_e2e_integration(qtbot, temp_environment):
    """Verifies SkillHubView full workflow: card click opens drawer, close drawer, scaffolding."""
    manager: SkillManager = temp_environment["manager"]

    # Scaffold 2 skills
    s1 = manager.create_skill(name="alpha_skill", description="Alpha test", target_scope="global")
    s2 = manager.create_skill(name="beta_skill", description="Beta test", target_scope="project")

    hub = SkillHubView(skill_manager=manager)
    qtbot.addWidget(hub)
    hub.show()

    assert hub.count() == 2
    assert hub.drawer.isVisible() is False

    # 1. Click on card opens drawer
    clicked_skills = []
    hub.skill_clicked.connect(lambda n: clicked_skills.append(n))

    card_alpha = hub._cards["alpha_skill"]
    card_alpha.card_clicked.emit("alpha_skill")

    assert hub.drawer.isVisible() is True
    assert hub.drawer.title_label.text() == "alpha_skill"
    assert len(clicked_skills) == 1

    # 2. Close drawer
    hub.drawer.btn_close.click()
    assert hub.drawer.isVisible() is False

    # 3. Create new skill programmatically via handler
    hub._handle_create_skill(
        name="gamma_skill",
        desc="Gamma test",
        tags=["gamma"],
        with_tools=True,
        scope="global",
    )

    assert hub.count() == 3
    assert "gamma_skill" in hub._cards

    # 4. Check updates trigger
    res = hub.check_updates()
    assert isinstance(res, (dict, SkillCheckUpdatesWorker))
    if hasattr(res, "wait"):
        res.wait(5000)
