# Specification: Issue #52 - Core Domain Models & SkillManager Local Import & Scaffolding Engine

## Context & Objectives
- **Issue**: #52 ([skill-mgr] 实现核心领域模型与 SkillManager 本地/ZIP导入及脚手架引擎)
- **Parent Epic**: #51 (ATBMind Skill Manager 全生命周期管理)
- **Sequence**: Step 1 of 5 (No prerequisites, blocks Step 2 and Step 3)
- **Goal**: Extend skill domain models in `atbmind_core/skills/schema.py`, enhance `SkillLoader` to handle `.source.json` and extended metadata, and implement the foundational `SkillManager` in `atbmind_core/skills/manager.py` with dual-tier storage, safe local folder & ZIP imports (Zip Slip defense), and standardized skill scaffolding.

---

## Scope & Architectural Design

### 1. Domain Models (`atbmind_core/skills/schema.py`)
- Define `SkillSourceInfo`:
  - `source_type`: Literal["github", "local", "scaffold", "builtin"] = "builtin"
  - `repo_url`: Optional[str] = None
  - `branch`: Optional[str] = "main"
  - `subpath`: Optional[str] = None
  - `installed_commit`: Optional[str] = None
  - `installed_at`: Optional[float] = None
  - `latest_upstream_commit`: Optional[str] = None
  - `has_update`: bool = False
  - `is_dirty`: bool = False
- Enhance `SkillMetadata`:
  - `name`: str
  - `description`: str = ""
  - `version`: str = "1.0.0"
  - `tags`: List[str] = []
  - `author`: Optional[str] = None
  - `repository`: Optional[str] = None
  - `enabled`: bool = True
  - `bound_roles`: List[str] = []
- Extend `Skill`:
  - `source`: Optional[SkillSourceInfo] = None
  - `scope`: Literal["project", "global"] = "project"

### 2. Loader Updates (`atbmind_core/skills/loader.py`)
- Read `.source.json` from the skill directory if present and populate `skill.source`.
- If `.source.json` is missing, infer default `SkillSourceInfo` based on location or metadata.
- Parse `author`, `repository`, `enabled`, and `bound_roles` from YAML frontmatter in `SKILL.md`.

### 3. SkillManager Service Core (`atbmind_core/skills/manager.py`)
- **Dual-Tier Resolution**:
  - `project_skills_dir`: default `Path.cwd() / "skills"`
  - `global_skills_dir`: default `~/.atbmind/skills`
- **Discovery**:
  - `discover_all() -> Dict[str, Skill]`: scans both directories, registers with `SkillRegistry`, and marks scope appropriately (`project` vs `global`).
- **Local Import (`import_from_local`)**:
  - Accepts local directory path or `.zip` file path.
  - Target scope: `"global"` (default) or `"project"`.
  - **Zip Slip Defense**: verifies canonical path of every extracted file stays strictly inside destination directory before extraction; rejects with `ValueError` on path traversal attempts (`../` or leading `/`).
  - Single-root unwrapping: unpacks cleanly if ZIP has a root container folder.
  - Ensures valid `SKILL.md` exists (or synthesizes a minimal one).
  - Writes `.source.json` with `source_type="local"`, timestamp, etc.
  - Registers into `SkillRegistry`.
- **Scaffolding (`create_skill`)**:
  - Generates template `SKILL.md` with standard YAML frontmatter and domain guideline sections.
  - If `with_tools=True`, creates executable `tools.py` with an illustrative `AgentTool` implementation.
  - Writes `.source.json` with `source_type="scaffold"`.
  - Registers into `SkillRegistry`.
- **Helper methods**:
  - `get_skill(name)`: retrieves from registry or disk.
  - `remove_skill(name, scope=None)`: safely deletes directory and unregisters.

---

## Comprehensive Implementation Checklist

- [ ] Task 1: Extend domain schemas (`SkillSourceInfo`, enhanced `SkillMetadata`, `Skill.source`, `Skill.scope`) in `atbmind_core/skills/schema.py`
- [ ] Task 2: Enhance `SkillLoader` in `atbmind_core/skills/loader.py` to support extended metadata and `.source.json`
- [ ] Task 3: Implement `SkillManager` service class in `atbmind_core/skills/manager.py` with dual-tier paths, discovery, and `.source.json` serialization
- [ ] Task 4: Implement `import_from_local` in `SkillManager` with directory copying, ZIP unwrapping, and strict Zip Slip security checks
- [ ] Task 5: Implement `create_skill` scaffolding in `SkillManager` generating compliant `SKILL.md` and executable `tools.py`
- [ ] Task 6: Export all new models and manager in `atbmind_core/skills/__init__.py`
- [ ] Task 7: Write comprehensive test suite in `tests/test_skills_manager.py` covering all features and security edge cases
- [ ] Task 8: Verify full regression test suite (`PYTHONPATH=src conda run -n ATBMind python -m pytest tests/`) and grill-me audit
