# Implementation Plan: Issue #52 - Core Domain Models & SkillManager Local Import & Scaffolding Engine

## Objective
Implement core domain models, safe local/ZIP import engine with Zip Slip defense, and scaffolding template generator for ATBMind Skill Manager.

---

## Proposed Changes

### 1. `atbmind_core/skills/schema.py`
- Add `SkillSourceInfo`:
  ```python
  class SkillSourceInfo(BaseModel):
      source_type: Literal["github", "local", "scaffold", "builtin"] = "builtin"
      repo_url: Optional[str] = None
      branch: Optional[str] = "main"
      subpath: Optional[str] = None
      installed_commit: Optional[str] = None
      installed_at: Optional[float] = None
      latest_upstream_commit: Optional[str] = None
      has_update: bool = False
      is_dirty: bool = False
  ```
- Add fields to `SkillMetadata`: `author`, `repository`, `enabled`, `bound_roles`.
- Add fields to `Skill`: `source`, `scope`.

### 2. `atbmind_core/skills/loader.py`
- Parse `author`, `repository`, `enabled`, and `bound_roles` from frontmatter.
- Check and load `.source.json` into `skill.source`.
- Set `skill.scope` based on path or parameters.

### 3. `atbmind_core/skills/manager.py` (New File)
- Define `SkillManager`:
  - `__init__(project_dir=None, global_dir=None, registry=None)`
  - `discover_all() -> Dict[str, Skill]`
  - `import_from_local(source_path, target_scope="global", skill_name=None, overwrite=False) -> Skill`
    - Directory copying or ZIP extraction.
    - Path traversal verification (Anti-Zip Slip).
    - Single-directory root unwrapping.
    - Write `.source.json`.
    - Register to `SkillRegistry`.
  - `create_skill(name, description="", tags=None, with_tools=True, target_scope="global", overwrite=False) -> Skill`
    - Generate compliant `SKILL.md`.
    - If `with_tools`, generate executable `tools.py` importing `AgentTool`.
    - Write `.source.json`.
    - Register to `SkillRegistry`.
  - `remove_skill(name, scope=None) -> bool`

### 4. `atbmind_core/skills/__init__.py`
- Re-export `SkillSourceInfo`, `SkillMetadata`, `Skill`, `SkillLoader`, `SkillRegistry`, `get_skill_registry`, `SkillManager`.

### 5. `tests/test_skills_manager.py` (New File)
- Test `SkillSourceInfo` serialization/deserialization.
- Test `SkillLoader` loading `.source.json` and extended metadata.
- Test `SkillManager.discover_all` with dual-tier mock dirs.
- Test `SkillManager.import_from_local` directory.
- Test `SkillManager.import_from_local` ZIP archive and unwrapping.
- Test `SkillManager.import_from_local` Zip Slip traversal rejection.
- Test `SkillManager.create_skill` with and without tools.
- Test `SkillManager.remove_skill`.

---

## Verification Plan

### Automated Tests
- Targeted test run:
  ```bash
  PYTHONPATH=. conda run -n ATBMind python -m pytest tests/test_skills_manager.py tests/test_skills.py
  ```
- Full test suite:
  ```bash
  PYTHONPATH=. conda run -n ATBMind python -m pytest tests/
  ```
