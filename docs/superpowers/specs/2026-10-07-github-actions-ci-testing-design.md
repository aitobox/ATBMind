# Technical Design Specification: GitHub Actions CI Testing

- **Author**: Antigravity Agent & Brain Zhang
- **Date**: 2026-10-07
- **Status**: Draft for Review
- **Target File(s)**:
  - `.github/workflows/test.yml`
  - `requirements.txt`

---

## 1. Context & Motivation

ATBMind currently has a full test suite with 179 test cases spanning `atbmind_core`, desktop widgets (PySide6 / `qtbot`), plugin architectures, and CLI packaging checks.
Previously, there were no automated GitHub Actions workflows in `.github/workflows/` to ensure regressions are caught during code review or commits.
Furthermore, while local virtual/conda environments have `pytest-qt` installed, `requirements.txt` lacked an explicit declaration for `pytest-qt`, which could lead to missing dependency failures in a clean CI environment.

This specification details the establishment of an automated, headless GitHub Actions CI pipeline executing the full test suite across macOS and Ubuntu runners.

---

## 2. Design Goals & Non-Goals

### Goals
1. **Automated Cross-Platform Testing**: Run unit and UI tests on both `ubuntu-latest` and `macos-latest` runners under Python 3.12.
2. **Deterministic Headless Qt Execution**: Guarantee PySide6 and `qtbot` run reliably in CI without physical display servers via `QT_QPA_PLATFORM=offscreen`.
3. **Optimized Build Times**: Leverage `actions/setup-python@v5` pip caching to minimize runner execution time.
4. **Complete Dependency Manifest**: Supplement `requirements.txt` with `pytest-qt>=4.4.0` so that any fresh environment can reproduce tests cleanly.
5. **Fail-Fast Isolation**: Set `fail-fast: false` on the test matrix so that OS-specific issues on one platform do not cancel runs on the other platform.

### Non-Goals
1. Automated DMG/App bundle building or release uploads (handled by separate release workflows).
2. Complex multi-container Docker workflows.
3. Code coverage badges or external SaaS integrations (YAGNI - focused purely on deterministic pass/fail testing).

---

## 3. Workflow Architecture

### 3.1 Trigger Conditions & Concurrency
- **Triggers**:
  - `push` to `main` branch.
  - `pull_request` targeting `main` branch.
  - `workflow_dispatch` (manual dispatch from GitHub UI).
- **Concurrency**:
  - Group: `${{ github.workflow }}-${{ github.ref }}`
  - `cancel-in-progress: true` to prevent redundant runner time on rapid pushes.

### 3.2 Strategy Matrix
- **Operating Systems**: `[ubuntu-latest, macos-latest]`
- **Python Version**: `["3.12"]`
- **Fail Fast**: `false`

### 3.3 Platform-Specific Requirements
- **Ubuntu (`ubuntu-latest`)**:
  - Requires headless dynamic libraries for PySide6 offscreen rendering:
    - `libegl1`, `libgl1`, `libxkbcommon-x11-0`, `libdbus-1-3`.
  - Installed via `sudo apt-get update && sudo apt-get install -y --no-install-recommends ...`.
- **macOS (`macos-latest`)**:
  - PySide6 supports offscreen mode natively without external X11 packages.

### 3.4 Test Execution Step
- Sets environment variables:
  - `QT_QPA_PLATFORM: offscreen`
  - `PYTHONPATH: .`
- Runs:
  ```bash
  python -m pytest tests/ -v
  ```

---

## 4. Detailed File Specifications

### 4.1 `.github/workflows/test.yml`
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

### 4.2 `requirements.txt`
Updated with `pytest-qt>=4.4.0`:
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

---

## 5. Verification & Acceptance Criteria

1. **Syntax Validation**:
   - YAML syntax of `.github/workflows/test.yml` must parse successfully using Python's `yaml.safe_load`.
2. **Dependency Correctness**:
   - `requirements.txt` contains all test requirements including `pytest-qt`.
3. **Local Offscreen Test Run**:
   - `QT_QPA_PLATFORM=offscreen conda run -n ATBMind python -m pytest tests/` executes and passes all 179 tests without display errors.
4. **Clean Git Status**:
   - All newly added files and edits tracked properly in Git.
