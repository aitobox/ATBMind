# Implementation Plan: Issue #53 - GitHub Repository & Subdirectory Import Engine and Upstream Version Updater

## Objective
Implement GitHub repository and subdirectory import mechanisms (with sparse-checkout and fallback), Git Commit SHA upstream update checking, and safe snapshot updates.

---

## Proposed Changes

### 1. `atbmind_core/skills/manager.py`
- Add `parse_github_url(url: str) -> Dict[str, Any]` function:
  - Supports `https://github.com/owner/repo`
  - Supports `https://github.com/owner/repo/tree/branch/subpath`
  - Supports `owner/repo` and `owner/repo@branch`
  - Returns `owner`, `repo`, `branch`, `subpath`, `clone_url`
- Add methods to `SkillManager`:
  - `import_from_github(url, target_scope="global", skill_name=None, overwrite=False) -> Skill`
    - Parses URL.
    - Clones using git sparse-checkout if subpath, or full shallow clone, or falls back to zipball download.
    - Captures `commit_sha`.
    - Validates `SKILL.md`.
    - Copies to destination.
    - Writes `.source.json` with `source_type="github"`.
    - Registers in `SkillRegistry`.
  - `check_updates(skill_names: Optional[List[str]] = None) -> Dict[str, bool]`
    - Queries `git ls-remote` for upstream SHA.
    - Compares with `installed_commit`.
    - Updates `.source.json` and memory state.
  - `update_skill(name: str) -> Skill`
    - Backs up current folder to `.backup/<name>_<timestamp>`.
    - Pulls latest version.
    - Updates `.source.json`.
    - Hot reloads skill.

### 2. `atbmind_core/skills/__init__.py`
- Export `parse_github_url`.

### 3. `tests/test_skills_updater.py` (New File)
- Test `parse_github_url` across URL permutations.
- Test `import_from_github` (with mock git/download).
- Test missing `SKILL.md` rejection.
- Test `check_updates` with mock `git ls-remote`.
- Test `update_skill` with snapshot backup in `.backup/`.

---

## Verification Plan
- Unit tests:
  ```bash
  PYTHONPATH=. conda run -n ATBMind python -m pytest tests/test_skills_updater.py tests/test_skills_manager.py
  ```
- Full suite:
  ```bash
  PYTHONPATH=. conda run -n ATBMind python -m pytest tests/
  ```
