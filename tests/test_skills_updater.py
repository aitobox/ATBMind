import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from atbmind_core.skills import (
    SkillManager,
    SkillRegistry,
    parse_github_url,
)


def test_parse_github_url():
    # 1. Base repository
    u1 = parse_github_url("https://github.com/aitobox/ATBMind")
    assert u1["owner"] == "aitobox"
    assert u1["repo"] == "ATBMind"
    assert u1["branch"] == "main"
    assert u1["subpath"] is None
    assert u1["clone_url"] == "https://github.com/aitobox/ATBMind.git"

    # 2. With .git suffix
    u2 = parse_github_url("https://github.com/aitobox/ATBMind.git")
    assert u2["repo"] == "ATBMind"

    # 3. Subdirectory in tree
    u3 = parse_github_url("https://github.com/xingkongliang/skills-manager/tree/dev/skills/manage-skills")
    assert u3["owner"] == "xingkongliang"
    assert u3["repo"] == "skills-manager"
    assert u3["branch"] == "dev"
    assert u3["subpath"] == "skills/manage-skills"

    # 4. Short form
    u4 = parse_github_url("aitobox/cool-agent")
    assert u4["owner"] == "aitobox"
    assert u4["repo"] == "cool-agent"
    assert u4["branch"] == "main"

    # 5. Short form with branch
    u5 = parse_github_url("aitobox/cool-agent@release-1.0")
    assert u5["owner"] == "aitobox"
    assert u5["repo"] == "cool-agent"
    assert u5["branch"] == "release-1.0"

    # 6. Invalid inputs
    with pytest.raises(ValueError):
        parse_github_url("")
    with pytest.raises(ValueError):
        parse_github_url("https://gitlab.com/foo/bar")
    with pytest.raises(ValueError):
        parse_github_url("invalid_identifier")


def test_import_from_github_success(tmp_path: Path):
    proj_dir = tmp_path / "proj"
    glob_dir = tmp_path / "glob"
    manager = SkillManager(project_dir=proj_dir, global_dir=glob_dir, registry=SkillRegistry())

    def fake_subprocess_run(cmd, *args, **kwargs):
        # When git clone is invoked, simulate creating a git repo with a SKILL.md
        if cmd[0] == "git" and cmd[1] == "clone":
            dest = Path(cmd[-1])
            dest.mkdir(parents=True, exist_ok=True)
            if "--sparse" in cmd:
                sub = dest / "skills" / "demo"
                sub.mkdir(parents=True, exist_ok=True)
                (sub / "SKILL.md").write_text("---\nname: github_demo\n---\n# Guide", encoding="utf-8")
            else:
                (dest / "SKILL.md").write_text("---\nname: github_repo_demo\n---\n# Guide", encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        elif cmd[0] == "git" and cmd[1] == "sparse-checkout":
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        elif cmd[0] == "git" and cmd[1] == "rev-parse":
            return subprocess.CompletedProcess(cmd, 0, stdout="commit_hash_123456\n", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    with patch("subprocess.run", side_effect=fake_subprocess_run):
        skill = manager.import_from_github(
            "https://github.com/sample/repo/tree/main/skills/demo",
            target_scope="global",
        )
        assert skill.metadata.name == "github_demo"
        assert skill.scope == "global"
        assert skill.source.source_type == "github"
        assert skill.source.installed_commit == "commit_hash_123456"
        assert skill.source.subpath == "skills/demo"
        assert (glob_dir / "github_demo" / ".source.json").exists()
        assert (glob_dir / "github_demo" / "SKILL.md").exists()


def test_import_from_github_missing_skill_md(tmp_path: Path):
    proj_dir = tmp_path / "proj"
    glob_dir = tmp_path / "glob"
    manager = SkillManager(project_dir=proj_dir, global_dir=glob_dir, registry=SkillRegistry())

    def fake_empty_clone(cmd, *args, **kwargs):
        if cmd[0] == "git" and cmd[1] == "clone":
            dest = Path(cmd[-1])
            dest.mkdir(parents=True, exist_ok=True)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    with patch("subprocess.run", side_effect=fake_empty_clone):
        with pytest.raises(ValueError, match="does not contain a valid SKILL.md"):
            manager.import_from_github("https://github.com/sample/empty-repo", target_scope="global")


def test_check_updates_and_update_skill(tmp_path: Path):
    proj_dir = tmp_path / "proj"
    glob_dir = tmp_path / "glob"
    manager = SkillManager(project_dir=proj_dir, global_dir=glob_dir, registry=SkillRegistry())

    # Create an initial installed github skill
    skill_dir = glob_dir / "updatable_skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("---\nname: updatable_skill\n---\nInitial content", encoding="utf-8")
    source_json = {
        "source_type": "github",
        "repo_url": "https://github.com/sample/repo.git",
        "branch": "main",
        "subpath": None,
        "installed_commit": "commit_v1",
        "installed_at": 1000.0,
        "latest_upstream_commit": "commit_v1",
        "has_update": False,
        "is_dirty": False,
    }
    (skill_dir / ".source.json").write_text(json.dumps(source_json), encoding="utf-8")

    manager.discover_all()

    # 1. Test check_updates when upstream has newer commit
    def fake_ls_remote(cmd, *args, **kwargs):
        if "ls-remote" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="commit_v2\trefs/heads/main\n", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    with patch("subprocess.run", side_effect=fake_ls_remote):
        updates = manager.check_updates(["updatable_skill"])
        assert updates.get("updatable_skill") is True
        updated_state = json.loads((skill_dir / ".source.json").read_text(encoding="utf-8"))
        assert updated_state["has_update"] is True
        assert updated_state["latest_upstream_commit"] == "commit_v2"

    # 2. Test update_skill creating backup snapshot and updating files
    def fake_update_clone(cmd, *args, **kwargs):
        if cmd[0] == "git" and cmd[1] == "clone":
            dest = Path(cmd[-1])
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "SKILL.md").write_text("---\nname: updatable_skill\n---\nUpdated content v2", encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        elif cmd[0] == "git" and cmd[1] == "rev-parse":
            return subprocess.CompletedProcess(cmd, 0, stdout="commit_v2\n", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    with patch("subprocess.run", side_effect=fake_update_clone):
        updated_skill = manager.update_skill("updatable_skill")
        assert updated_skill.metadata.name == "updatable_skill"
        assert "Updated content v2" in updated_skill.domain_prompt

        # Assert .backup snapshot was created
        backup_dir = glob_dir / ".backup"
        assert backup_dir.is_dir()
        backup_snapshots = list(backup_dir.iterdir())
        assert len(backup_snapshots) == 1
        assert "updatable_skill_" in backup_snapshots[0].name
        assert (backup_snapshots[0] / "SKILL.md").read_text(encoding="utf-8") == "---\nname: updatable_skill\n---\nInitial content"
