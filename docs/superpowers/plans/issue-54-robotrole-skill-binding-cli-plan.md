# Implementation Plan: Issue #54 - RobotRole Dynamic Skill Binding & CLI Toolchain

## Objective
Implement dynamic skill binding and unbinding on RobotRole definitions with live reload of system prompts and tools, add `check_requirements` environment diagnostics, and build `scripts/atbmind_skills.py` CLI.

---

## Proposed Changes

### 1. `atbmind_core/roles/registry.py`
- Add `reload_role(role_id: str) -> Optional[RobotRole]`:
  - Retrieves existing role's `role_dir` or finds role in scanned directory.
  - Re-reads `role.yaml` through `RoleLoader.load_from_dir`.
  - Re-registers in `self._roles`.
  - Returns reloaded `RobotRole`.

### 2. `atbmind_core/skills/manager.py`
- In `__init__`, add `roles_dir: Optional[Path | str] = None` and `role_registry: Optional[RoleRegistry] = None`.
- Add `bind_skill_to_role(role_id: str, skill_name: str) -> bool`:
  - Updates `roles/<role_id>/role.yaml` `skills` list.
  - Calls `role_registry.reload_role(role_id)`.
  - Syncs `bound_roles` on the skill object and `SKILL.md`.
- Add `unbind_skill_from_role(role_id: str, skill_name: str) -> bool`:
  - Removes `skill_name` from `roles/<role_id>/role.yaml`.
  - Calls `role_registry.reload_role(role_id)`.
  - Syncs `bound_roles` on skill.
- Add `check_requirements(skill_name: str) -> Dict[str, Any]`:
  - Inspects `requirements.txt`.
  - Uses `importlib.metadata.version` to check package status.
  - Returns `{"has_requirements": bool, "missing": [...], "satisfied": [...]}`.

### 3. `scripts/atbmind_skills.py` (New File)
- CLI program using `argparse` supporting commands:
  - `list [--role ROLE] [--json]`
  - `show SKILL [--json]`
  - `install URL_OR_PATH [--target {global,project}] [--name NAME] [--overwrite] [--json]`
  - `new NAME [--desc DESC] [--tags TAGS] [--with-tools / --no-tools] [--target {global,project}] [--json]`
  - `check [--json]`
  - `update [SKILL] [--all] [--json]`
  - `bind ROLE SKILL [--json]`
  - `unbind ROLE SKILL [--json]`
  - `remove SKILL [--target {global,project}] [--json]`

### 4. `tests/test_skills_role_binding.py` (New File)
- Test `bind_skill_to_role` updates `role.yaml` and reloads prompt/tools.
- Test `unbind_skill_from_role`.
- Test `check_requirements` on present and missing dependencies.

### 5. `tests/test_skills_cli.py` (New File)
- Test CLI invocation of all subcommands using `subprocess.run` or runner with exit code checks and JSON parsing.

---

## Verification Plan
- Unit tests:
  ```bash
  PYTHONPATH=. conda run -n ATBMind python -m pytest tests/test_skills_role_binding.py tests/test_skills_cli.py
  ```
- Full suite:
  ```bash
  PYTHONPATH=. conda run -n ATBMind python -m pytest tests/
  ```
