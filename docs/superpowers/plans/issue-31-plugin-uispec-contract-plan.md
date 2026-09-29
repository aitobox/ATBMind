# Issue #31 Implementation Plan: PluginUISpec Contract & ATBDraw `get_ui_spec()`

## Task 1: Schema & Base SPI Contract (TDD)
- **Files**:
  - `tests/test_plugin_schemas.py`
  - `atbmind_core/plugins/schemas.py`
  - `atbmind_core/plugins/base.py`
- **Steps**:
  1. Add `test_plugin_ui_spec_schema_and_defaults` and verify default `ATBMindPlugin.get_ui_spec() is None` in `tests/test_plugin_schemas.py`.
  2. Run `pytest tests/test_plugin_schemas.py` to confirm failure (Red).
  3. Define `PluginUISpec` in `atbmind_core/plugins/schemas.py` and `get_ui_spec()` in `atbmind_core/plugins/base.py`.
  4. Run `pytest tests/test_plugin_schemas.py` to confirm pass (Green).

## Task 2: `DrawPlugin.get_ui_spec()` Implementation (TDD)
- **Files**:
  - `tests/test_plugin_draw.py`
  - `plugins/draw/plugin.py`
- **Steps**:
  1. Add `test_draw_plugin_get_ui_spec()` in `tests/test_plugin_draw.py` checking `plugin_id`, `display_name`, `icon`, `models`, `aspect_ratios`, `styles`, `templates`, and JSON/dict serialization.
  2. Run `pytest tests/test_plugin_draw.py` to confirm failure (Red).
  3. Implement `DrawPlugin.get_ui_spec()` and `DRAW_UI_MODELS`, `DRAW_UI_ASPECT_RATIOS`, `DRAW_UI_STYLES` in `plugins/draw/plugin.py`.
  4. Run `pytest tests/test_plugin_draw.py tests/test_plugin_schemas.py` to confirm pass (Green).

## Task 3: Full Regression Suite & Code Review
- Run `conda run -n ATBMind python -m pytest tests/ -v` and verify 100% pass.
