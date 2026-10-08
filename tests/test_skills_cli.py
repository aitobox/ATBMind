import json
import subprocess
import sys
from pathlib import Path
import pytest
import yaml

CLI_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "atbmind_skills.py"


def run_cli(*args, **kwargs) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(CLI_SCRIPT)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def test_cli_new_list_show_and_remove(tmp_path: Path):
    proj_dir = tmp_path / "proj_skills"
    glob_dir = tmp_path / "glob_skills"
    roles_dir = tmp_path / "roles"
    proj_dir.mkdir()
    glob_dir.mkdir()
    roles_dir.mkdir()

    base_args = [
        "--project-dir", str(proj_dir),
        "--global-dir", str(glob_dir),
        "--roles-dir", str(roles_dir),
    ]

    # 1. New skill via CLI
    res = run_cli(*base_args, "new", "cli_demo", "--desc", "CLI created skill", "--tags", "cli,test", "--json")
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["success"] is True
    assert data["name"] == "cli_demo"

    # 2. List skills via CLI
    res_list = run_cli(*base_args, "list", "--json")
    assert res_list.returncode == 0
    skills = json.loads(res_list.stdout)
    assert any(s["name"] == "cli_demo" for s in skills)

    # 3. Show skill via CLI
    res_show = run_cli(*base_args, "show", "cli_demo", "--json")
    assert res_show.returncode == 0
    details = json.loads(res_show.stdout)
    assert details["name"] == "cli_demo"
    assert details["description"] == "CLI created skill"
    assert "cli" in details["tags"]
    assert len(details["tools"]) == 1

    # 4. Remove skill via CLI
    res_rm = run_cli(*base_args, "remove", "cli_demo", "--json")
    assert res_rm.returncode == 0
    rm_data = json.loads(res_rm.stdout)
    assert rm_data["success"] is True

    # 5. List should be empty of cli_demo
    res_list2 = run_cli(*base_args, "list", "--json")
    skills2 = json.loads(res_list2.stdout)
    assert not any(s["name"] == "cli_demo" for s in skills2)


def test_cli_bind_and_unbind(tmp_path: Path):
    proj_dir = tmp_path / "proj_skills"
    glob_dir = tmp_path / "glob_skills"
    roles_dir = tmp_path / "roles"
    proj_dir.mkdir()
    glob_dir.mkdir()
    roles_dir.mkdir()

    # Create dummy role
    role_dir = roles_dir / "assistant"
    role_dir.mkdir()
    (role_dir / "role.yaml").write_text(yaml.safe_dump({
        "role_id": "assistant",
        "name": "助理",
        "skills": [],
    }), encoding="utf-8")

    base_args = [
        "--project-dir", str(proj_dir),
        "--global-dir", str(glob_dir),
        "--roles-dir", str(roles_dir),
    ]

    # Create skill
    run_cli(*base_args, "new", "tool_helper", "--json")

    # Bind
    res_bind = run_cli(*base_args, "bind", "assistant", "tool_helper", "--json")
    assert res_bind.returncode == 0
    bind_data = json.loads(res_bind.stdout)
    assert bind_data["success"] is True

    # Verify role file on disk
    role_yaml = yaml.safe_load((role_dir / "role.yaml").read_text(encoding="utf-8"))
    assert "tool_helper" in role_yaml["skills"]

    # Filter list by role
    res_role_list = run_cli(*base_args, "list", "--role", "assistant", "--json")
    role_skills = json.loads(res_role_list.stdout)
    assert any(s["name"] == "tool_helper" for s in role_skills)

    # Unbind
    res_unbind = run_cli(*base_args, "unbind", "assistant", "tool_helper", "--json")
    assert res_unbind.returncode == 0
    unbind_data = json.loads(res_unbind.stdout)
    assert unbind_data["success"] is True

    # Verify disk
    role_yaml_after = yaml.safe_load((role_dir / "role.yaml").read_text(encoding="utf-8"))
    assert "tool_helper" not in role_yaml_after["skills"]
