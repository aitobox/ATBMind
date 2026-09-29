# SidebarWidget with Session List & Settings Action Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete, polish, and thoroughly test the Apple HIG-compliant `SidebarWidget` component and its session list for ATBMind (Issue #33).

**Architecture:** A standalone PySide6 QWidget (`SidebarWidget`) hosting branding, high-priority new session button, custom QListWidget with `SessionItemWidget` and `LoadingSpinner`, and bottom settings action bar.

**Tech Stack:** Python 3.12+, PySide6 6.11+, pytest-qt (`qtbot`).

**Spec:** [docs/superpowers/specs/issue-33-sidebar-widget-session-list-spec.md](docs/superpowers/specs/issue-33-sidebar-widget-session-list-spec.md)

## Global Constraints
- Target macOS native patterns, PySide6, Python 3.12+.
- Test command: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_sidebar_widget.py`.
- No global pip install; run inside ATBMind environment.
- Preserve backward compatibility with `ATBMindMainWindow` and `UIStateManager`.

---

### Task 1: Polish SidebarWidget and LoadingSpinner

**Files:**
- Modify: `apps/atbmind_desktop/widgets/sidebar.py`
- Test: `tests/test_sidebar_widget.py`

**Interfaces:**
- Consumes: `SessionRecord` from `atbmind_core.plugins.schemas`.
- Produces:
  - `LoadingSpinner(QWidget)`: with `start()`, `stop()`, `is_spinning()`.
  - `SessionItemWidget(QWidget)`: with `update_data(session, in_flight)`.
  - `SidebarWidget(QWidget)`: with signals `new_session_requested`, `session_selected(str)`, `session_rename_requested(str, str)`, `session_delete_requested(str)`, `open_settings_requested`.
  - Public methods: `set_sessions`, `add_session`, `update_session`, `remove_session`, `select_session`, `set_in_flight`, `is_in_flight`, `create_context_menu`.

- [ ] **Step 1: Write failing test in `tests/test_sidebar_widget.py`**
- [ ] **Step 2: Run pytest to verify failure**
- [ ] **Step 3: Implement `LoadingSpinner` and enhancements in `apps/atbmind_desktop/widgets/sidebar.py`**
- [ ] **Step 4: Run pytest to verify pass**
- [ ] **Step 5: Commit changes with git**

---

### Task 2: Comprehensive Test Suite for SidebarWidget

**Files:**
- Create: `tests/test_sidebar_widget.py`

**Interfaces:**
- Exercises all signals, slot interactions, context menu operations, and in-flight toggling using `qtbot`.

- [ ] **Step 1: Write all test cases in `tests/test_sidebar_widget.py`**
- [ ] **Step 2: Run pytest on `tests/test_sidebar_widget.py`**
- [ ] **Step 3: Run project-wide test suite `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/`**
- [ ] **Step 4: Commit test suite with git**
