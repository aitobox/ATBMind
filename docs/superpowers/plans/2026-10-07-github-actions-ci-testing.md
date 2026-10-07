# GitHub Actions CI Testing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish automated GitHub Actions CI workflow to run the full pytest test suite across macOS and Ubuntu runners under Python 3.12.

**Architecture:** Add `.github/workflows/test.yml` using a dual-OS matrix (`ubuntu-latest`, `macos-latest`), with pip caching, headless Qt system dependencies on Linux, and `QT_QPA_PLATFORM=offscreen`. Update `requirements.txt` to include `pytest-qt>=4.4.0`. Add local test verifying CI workflow syntax and integrity.

**Tech Stack:** GitHub Actions, Python 3.12, PySide6, pytest, pytest-qt, PyYAML.

**Spec:** [docs/superpowers/specs/2026-10-07-github-actions-ci-testing-design.md](file:///docs/superpowers/specs/2026-10-07-github-actions-ci-testing-design.md)

## Global Constraints

- Python floor: Python 3.12+
- PySide6 test execution mode: `QT_QPA_PLATFORM=offscreen`
- CI runner OS matrix: `ubuntu-latest` and `macos-latest`
- Runner fail-fast behavior: `fail-fast: false`
- CI test command: `python -m pytest tests/ -v`

## Review Focus

- Missing Linux X11/EGL libraries causes PySide6 import crash on Ubuntu runner: Handled via explicit `apt-get install` step for `libegl1`, `libgl1`, `libxkbcommon-x11-0`, `libdbus-1-3`.
- Workflow YAML syntax indentation or schema errors: Handled by automated static verification test in `tests/test_ci_workflow.py`.
- Missing `pytest-qt` in clean pip environment: Handled by adding `pytest-qt>=4.4.0` to `requirements.txt`.
- GUI tests hanging or failing due to lack of display: Handled by setting `QT_QPA_PLATFORM: offscreen` in job step env.
- Redundant concurrent CI runs wasting runner minutes: Handled by `concurrency: cancel-in-progress: true`.

---

### Task 1: Update Dependency Manifest (`requirements.txt`)

**Files:**
- Modify: `requirements.txt:7-9`
- Test: `tests/` (existing test suite)

**Interfaces:**
- Consumes: None
- Produces: `pytest-qt>=4.4.0` in `requirements.txt`

- [ ] **Step 1: Check existing requirements.txt and verify missing pytest-qt**

Check `requirements.txt` lines 1-9 to verify `pytest-qt` is not yet declared.

- [ ] **Step 2: Append `pytest-qt>=4.4.0` to `requirements.txt`**

Update `requirements.txt` to include:
```text
fastapi>=0.110.0
uvicorn>=0.28.0
pydantic>=2.6.0
pyyaml>=6.0.1
httpx>=0.27.0
pyside6>=6.6.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
pytest-qt>=4.4.0
```

- [ ] **Step 3: Verify requirements installation consistency**

Run: `conda run -n ATBMind python -m pip check`
Expected: Output indicates `No broken requirements found.`

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "build: add pytest-qt to requirements.txt"
```

---

### Task 2: Create Workflow Syntax & Integrity Test

**Files:**
- Create: `tests/test_ci_workflow.py`
- Target: `.github/workflows/test.yml`

**Interfaces:**
- Consumes: `.github/workflows/test.yml`
- Produces: Pytest verification validating YAML syntax, trigger rules, OS matrix, and environment variables.

- [ ] **Step 1: Write the failing test for workflow file existence and structure**

Create `tests/test_ci_workflow.py`:
```python
from pathlib import Path
import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT_DIR / ".github" / "workflows" / "test.yml"


def test_workflow_file_exists_and_valid_yaml():
    assert WORKFLOW_PATH.is_file(), ".github/workflows/test.yml does not exist"
    data = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    assert data is not None
    assert data.get("name") == "Tests"


def test_workflow_triggers_and_concurrency():
    data = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    # Triggers
    assert "push" in data.get("on", {})
    assert "pull_request" in data.get("on", {})
    assert "workflow_dispatch" in data.get("on", {})
    assert "main" in data["on"]["push"]["branches"]
    assert "main" in data["on"]["pull_request"]["branches"]

    # Concurrency
    concurrency = data.get("concurrency", {})
    assert concurrency.get("cancel-in-progress") is True


def test_workflow_matrix_and_offscreen():
    data = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    jobs = data.get("jobs", {})
    assert "pytest" in jobs
    pytest_job = jobs["pytest"]

    matrix = pytest_job.get("strategy", {}).get("matrix", {})
    assert "ubuntu-latest" in matrix.get("os", [])
    assert "macos-latest" in matrix.get("os", [])
    assert "3.12" in matrix.get("python-version", [])

    # Check test step environment
    steps = pytest_job.get("steps", [])
    test_step = next((s for s in steps if "Run pytest" in s.get("name", "")), None)
    assert test_step is not None, "Run pytest step not found"
    assert test_step.get("env", {}).get("QT_QPA_PLATFORM") == "offscreen"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n ATBMind python -m pytest tests/test_ci_workflow.py -v`
Expected: FAIL because `.github/workflows/test.yml` does not exist yet.

- [ ] **Step 3: Commit the test**

```bash
git add tests/test_ci_workflow.py
git commit -m "test: add workflow static validation tests"
```

---

### Task 3: Create GitHub Actions Workflow File & Verify End-to-End

**Files:**
- Create: `.github/workflows/test.yml`
- Test: `tests/test_ci_workflow.py` and full test suite

**Interfaces:**
- Consumes: Requirements from Task 1, Test assertions from Task 2
- Produces: Ready-to-deploy `.github/workflows/test.yml`

- [ ] **Step 1: Create directory `.github/workflows` and file `.github/workflows/test.yml`**

Write `.github/workflows/test.yml`:
```yaml
name: Tests

on:
  push:
    branches:
      - main
  pull_request:
    branches:
      - main
  workflow_dispatch:

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  pytest:
    name: pytest (${{ matrix.os }}, py${{ matrix.python-version }})
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest]
        python-version: ["3.12"]

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Install Linux system dependencies for Qt
        if: runner.os == 'Linux'
        run: |
          sudo apt-get update
          sudo apt-get install -y --no-install-recommends \
            libegl1 \
            libgl1 \
            libxkbcommon-x11-0 \
            libdbus-1-3

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: 'pip'

      - name: Install Python dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run pytest test suite
        env:
          QT_QPA_PLATFORM: offscreen
          PYTHONPATH: .
        run: |
          python -m pytest tests/ -v
```

- [ ] **Step 2: Run the workflow integrity test to verify it passes**

Run: `conda run -n ATBMind python -m pytest tests/test_ci_workflow.py -v`
Expected: PASS (3 passed)

- [ ] **Step 3: Run the full test suite in offscreen mode to ensure zero regressions**

Run: `QT_QPA_PLATFORM=offscreen conda run -n ATBMind python -m pytest tests/ -v`
Expected: PASS (182 passed: 179 existing + 3 new workflow tests)

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/test.yml
git commit -m "ci: add GitHub Actions cross-platform test workflow"
```
