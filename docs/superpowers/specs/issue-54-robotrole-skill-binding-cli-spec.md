# Specification: Issue #54 - RobotRole Dynamic Skill Binding & CLI Toolchain

## Context & Objectives
- **Issue**: #54 ([skill-mgr] 实现 RobotRole 动态装备热重载机制与 CLI 工具链)
- **Parent Epic**: #51 (ATBMind Skill Manager 全生命周期管理)
- **Sequence**: Step 3 of 5 (Depends on #52, #53; blocks Step 4)
- **Goal**: Enable bidirectional binding and unbinding between Skills and RobotRole expert agents with instant hot-reloading (updating prompts and tools dynamically), add dependency diagnostic checks (`check_requirements`), and develop the full-featured `scripts/atbmind_skills.py` CLI utility.

---

## Architectural Design

### 1. Dynamic Role Binding & Hot-Reload (`SkillManager` & `RoleRegistry`)
- `bind_skill_to_role(role_id: str, skill_name: str) -> bool`:
  - Locates `roles/<role_id>/role.yaml`.
  - Appends `skill_name` to `skills` list if not already present.
  - Atomically writes back `role.yaml`.
  - Calls `role_registry.reload_role(role_id)` to re-parse the role into memory.
  - Ensures the role's system prompt and tools dynamically reflect the newly attached skill.
  - Updates `bound_roles` in skill metadata.
- `unbind_skill_from_role(role_id: str, skill_name: str) -> bool`:
  - Removes `skill_name` from `roles/<role_id>/role.yaml`.
  - Atomically saves `role.yaml`.
  - Reloads role in `role_registry`.
  - Updates `bound_roles` in skill metadata.

### 2. Dependency Diagnostics (`check_requirements`)
- `check_requirements(skill_name: str) -> Dict[str, Any]`:
  - Finds `requirements.txt` in the skill's root directory.
  - Parses required packages.
  - Uses `importlib.metadata` to verify whether required packages are installed in the active Python environment.
  - Returns `{"has_requirements": bool, "missing": List[str], "satisfied": List[str]}`.

### 3. Command-Line Interface (`scripts/atbmind_skills.py`)
- Standard subcommands:
  - `list`: List all installed skills (optional `--role <role_id>`, `--json`)
  - `show <skill>`: Inspect metadata, guidelines, tools, bound roles, and requirements status (optional `--json`)
  - `install <url_or_path>`: Install from GitHub URL, local folder, or ZIP archive (supports `--target`, `--name`, `--overwrite`, `--json`)
  - `new <name>`: Create new standardized skill package (supports `--desc`, `--tags`, `--with-tools`, `--target`, `--json`)
  - `check`: Check upstream GitHub updates across all skills (supports `--json`)
  - `update [<skill>]`: Pull latest upstream updates (supports `--all`, `--json`)
  - `bind <role> <skill>`: Equip skill to an expert role (supports `--json`)
  - `unbind <role> <skill>`: Unequip skill from an expert role (supports `--json`)
  - `remove <skill>`: Delete and unregister skill (supports `--target`, `--json`)

---

## Comprehensive Implementation Checklist

- [ ] Task 1: Add `reload_role` method to `RoleRegistry` in `atbmind_core/roles/registry.py`
- [ ] Task 2: Implement `bind_skill_to_role` and `unbind_skill_from_role` in `SkillManager`
- [ ] Task 3: Implement `check_requirements` in `SkillManager` for skill environment diagnostics
- [ ] Task 4: Develop `scripts/atbmind_skills.py` CLI tool covering all subcommands and JSON output
- [ ] Task 5: Write unit tests in `tests/test_skills_role_binding.py` verifying YAML persistence and prompt/tool updates
- [ ] Task 6: Write unit tests in `tests/test_skills_cli.py` verifying all CLI command behaviors and exit codes
- [ ] Task 7: Verify full test suite (`PYTHONPATH=src conda run -n ATBMind python -m pytest tests/`) and grill-me audit
