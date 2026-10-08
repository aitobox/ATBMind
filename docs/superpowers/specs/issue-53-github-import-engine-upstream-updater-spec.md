# Specification: Issue #53 - GitHub Repository & Subdirectory Import Engine and Upstream Version Updater

## Context & Objectives
- **Issue**: #53 ([skill-mgr] 实现 GitHub 仓库与子目录导入引擎及上游版本检测器)
- **Parent Epic**: #51 (ATBMind Skill Manager 全生命周期管理)
- **Sequence**: Step 2 of 5 (Depends on #52, blocks Step 3)
- **Goal**: Implement GitHub URL parsing, Git sparse-checkout and archive fallback for repository/subdirectory downloads, remote Git Commit SHA differential detection (`check_updates`), and safe snapshot backup update execution (`update_skill`).

---

## Architectural Design

### 1. GitHub URL Parsing (`parse_github_url`)
Support full and abbreviated GitHub resource addresses:
- `https://github.com/owner/repo`
- `https://github.com/owner/repo.git`
- `https://github.com/owner/repo/tree/branch_name/path/to/skill`
- Short forms: `owner/repo`, `owner/repo@branch`, `owner/repo/tree/branch/subpath`
Output schema:
- `owner`: str
- `repo`: str
- `branch`: Optional[str]
- `subpath`: Optional[str]
- `clone_url`: str (e.g. `https://github.com/owner/repo.git`)

### 2. GitHub Downloader & Importer (`import_from_github`)
- Parameters: `url: str`, `target_scope: Literal["project", "global"] = "global"`, `skill_name: Optional[str] = None`, `overwrite: bool = False`
- Strategy:
  - If `subpath` exists:
    - Attempt `git clone --depth 1 --filter=blob:none --sparse` into a temporary directory.
    - Set sparse checkout for `subpath`.
    - Retrieve commit SHA via `git rev-parse HEAD`.
    - Fallback: download zip archive of the repository branch and extract subpath.
  - If whole repository:
    - `git clone --depth 1` into temporary directory or download archive.
  - Ensure candidate directory has `SKILL.md` (raise `ValueError` if missing or invalid).
  - Target placement: `dest_dir = get_skills_dir(target_scope) / resolved_name`.
  - Handle conflict / overwrite.
  - Write `.source.json` with `source_type="github"`, `installed_commit`, `branch`, `subpath`, `installed_at`, etc.
  - Load and register in `SkillRegistry`.

### 3. Upstream Version Detection (`check_updates`)
- Scan all registered skills with `source.source_type == "github"`.
- Query upstream remote SHA via `git ls-remote <repo_url> refs/heads/<branch>`.
- If remote SHA differs from `installed_commit`:
  - Mark `has_update = True` and `latest_upstream_commit = remote_sha`.
  - Atomically save to `.source.json`.
- Return summary map `{skill_name: has_update}`.

### 4. Safe Snapshot Update Execution (`update_skill`)
- Parameter: `name: str`
- Verification: ensure skill exists and has `source_type == "github"`.
- Snapshot backup: copy current skill directory to `.backup/<name>_<timestamp>`.
- Re-download from upstream URL at latest commit and overwrite skill directory.
- Update `.source.json` with `installed_commit = latest_upstream_commit`, `has_update = False`.
- Hot-reload skill via `SkillLoader.load_from_dir` and update `SkillRegistry`.

---

## Comprehensive Implementation Checklist

- [ ] Task 1: Implement `parse_github_url` utility supporting full URLs and short syntax
- [ ] Task 2: Implement `import_from_github` in `SkillManager` with sparse-checkout and archive fallback
- [ ] Task 3: Ensure strict `SKILL.md` verification and `.source.json` persistence for GitHub sources
- [ ] Task 4: Implement `check_updates` in `SkillManager` using `git ls-remote` SHA comparison
- [ ] Task 5: Implement `update_skill` in `SkillManager` with `.backup/` snapshots and hot-reload
- [ ] Task 6: Write unit tests in `tests/test_skills_updater.py` with mock Git subprocess commands
- [ ] Task 7: Verify all project tests pass (`PYTHONPATH=src conda run -n ATBMind python -m pytest tests/`) and grill-me audit
