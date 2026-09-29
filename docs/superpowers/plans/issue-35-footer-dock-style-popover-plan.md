# [UI-Component] Implement Pluggable FooterDock & StylePopover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the pluggable docked footer container featuring dynamic plugin control bar, Doubao-style art styles popover menu, image attachment chip, and auto-resizing prompt input.

**Architecture:** A modular PySide6 desktop UI component divided into `StylePopover` (popup grid style selector) and `FooterDock` (bottom dock holding dynamic plugin bar, prompt input, attachment chip with thumbnail, and send/stop toggle). Follows Apple HIG principles and integrates seamlessly with `ATBMindMainWindow` and plugin specs.

**Tech Stack:** Python 3.12+, PySide6 (QtCore, QtGui, QtWidgets), pytest, pytest-qt.

**Spec:** `docs/superpowers/specs/issue-35-footer-dock-style-popover-spec.md`

## Global Constraints
- Target macOS native patterns, PySide6, Python 3.12+.
- Python environment: `conda run -n ATBMind python -m pytest tests/`
- Zero third-party dependencies outside standard project environment.
- Preserve existing public API and signal signatures expected by `ATBMindMainWindow`.

---

### Task 1: Create `apps/atbmind_desktop/widgets/style_popover.py`

**Files:**
- Create: `apps/atbmind_desktop/widgets/style_popover.py`
- Test: `tests/test_footer_dock.py`

**Interfaces:**
- Consumes: `DRAW_UI_STYLES` from `plugins.draw.plugin`
- Produces: `StylePopover(QFrame)`
  - Signal: `style_selected = Signal(str, str)` (style_id, style_name)
  - Method: `show_at_widget(anchor_widget: QWidget)`
  - Method: `set_selected_style(style_id: str)`
  - Method: `get_selected_style() -> str`

- [ ] **Step 1: Write failing test in `tests/test_footer_dock.py` for StylePopover**
- [ ] **Step 2: Run test to verify it fails (`ModuleNotFoundError` or similar)**
- [ ] **Step 3: Implement `StylePopover` in `apps/atbmind_desktop/widgets/style_popover.py`**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Verify syntax and exports**

---

### Task 2: Upgrade `apps/atbmind_desktop/widgets/footer_dock.py`

**Files:**
- Modify: `apps/atbmind_desktop/widgets/footer_dock.py`
- Test: `tests/test_footer_dock.py`

**Interfaces:**
- Consumes: `StylePopover` from `apps.atbmind_desktop.widgets.style_popover`
- Produces: `FooterDock(QWidget)`
  - Signals: `submit_requested`, `plugin_changed`, `stop_requested`, `attachment_changed`
  - Methods: `load_plugin`, `unload_plugin`, `get_plugin_state`, `set_plugin_state`, `set_attachment`, `clear_attachment`, `get_attachment`, `set_prompt_text`, `get_prompt_text`, `set_busy`, `is_busy`
  - Drag and drop: accept image file drops and render AttachmentChip

- [ ] **Step 1: Write failing tests in `tests/test_footer_dock.py` for AttachmentChip thumbnail, StylePopover trigger, drag & drop, and busy state**
- [ ] **Step 2: Run tests to verify failures**
- [ ] **Step 3: Update `footer_dock.py` with StylePopover integration, thumbnail rendering in AttachmentChip, drag-and-drop events, and `set_busy` toggle**
- [ ] **Step 4: Run tests to verify they pass**

---

### Task 3: Comprehensive Test Suite & Integration Verification

**Files:**
- Create/Extend: `tests/test_footer_dock.py`

- [ ] **Step 1: Expand tests in `tests/test_footer_dock.py` to cover all edge cases (empty prompts, shift+enter, key events, clearing attachments, plugin toggles)**
- [ ] **Step 2: Run `conda run -n ATBMind python -m pytest tests/test_footer_dock.py`**
- [ ] **Step 3: Run full repository test suite `conda run -n ATBMind python -m pytest tests/` to verify zero regressions**
- [ ] **Step 4: Advance state to `reviewing` and trigger `atb-github-code-reviewer`**
