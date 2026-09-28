import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from atbmind_core.plugins.base import ATBMindPlugin
from atbmind_core.plugins.schemas import TemplateMetadata, WorkflowStep, WorkflowResult
from atbmind_core.plugins.exceptions import (
    PluginNotFoundError,
    PluginValidationError,
    PluginLoadError,
)
from atbmind_core.plugins.registry import PluginRegistry, get_plugin_registry

class DummyPlugin(ATBMindPlugin):
    def __init__(self, p_id: str = "dummy", ver: str = "0.1.0"):
        self._id = p_id
        self._ver = ver
        self.initialized = False

    @property
    def plugin_id(self) -> str:
        return self._id

    @property
    def version(self) -> str:
        return self._ver

    def initialize(self, config: Dict[str, Any]) -> None:
        self.initialized = True

    def get_templates(self) -> List[TemplateMetadata]:
        return []

    def extract_context_entities(self, raw_input: Any) -> Dict[str, Any]:
        return {}

    def get_domain_prompt_injection(self) -> str:
        return "Dummy domain prompt."

    def execute_workflow_step(self, step: WorkflowStep, context: Dict[str, Any]) -> WorkflowResult:
        return WorkflowResult(step=step.step, success=True)

def test_manual_registration_and_retrieval():
    """Verify manual registration, lookup, listing, and unregistration."""
    registry = PluginRegistry()
    p1 = DummyPlugin("plugin_a")
    p2 = DummyPlugin("plugin_b")

    registry.register_plugin(p1)
    registry.register_plugin(p2)

    assert p1.initialized is True
    assert p2.initialized is True
    assert registry.list_plugins() == ["plugin_a", "plugin_b"]
    assert registry.get_plugin("plugin_a") is p1

    registry.unregister_plugin("plugin_a")
    assert registry.list_plugins() == ["plugin_b"]

    with pytest.raises(PluginNotFoundError):
        registry.get_plugin("plugin_a")

def test_duplicate_and_not_found_handling():
    """Verify duplicate IDs trigger PluginValidationError and non-existent IDs trigger PluginNotFoundError."""
    registry = PluginRegistry()
    p1 = DummyPlugin("p1")
    registry.register_plugin(p1)

    # Duplicate registration
    p1_dup = DummyPlugin("p1")
    with pytest.raises(PluginValidationError):
        registry.register_plugin(p1_dup)

    # Not found lookup
    with pytest.raises(PluginNotFoundError):
        registry.get_plugin("non_existent")

def test_dynamic_directory_scan():
    """Verify scanning directory discovers ATBMindPlugin subclasses."""
    temp_dir = tempfile.mkdtemp()
    try:
        # Create a valid plugin package
        mock_pkg = Path(temp_dir) / "mock_draw"
        mock_pkg.mkdir(parents=True)
        (mock_pkg / "__init__.py").write_text("", encoding="utf-8")
        plugin_code = """
from atbmind_core.plugins.base import ATBMindPlugin
from atbmind_core.plugins.schemas import TemplateMetadata, WorkflowStep, WorkflowResult

class AutoDiscoveredPlugin(ATBMindPlugin):
    @property
    def plugin_id(self) -> str:
        return "auto_draw"

    @property
    def version(self) -> str:
        return "1.0.0"

    def initialize(self, config):
        pass

    def get_templates(self):
        return []

    def extract_context_entities(self, raw_input):
        return {}

    def get_domain_prompt_injection(self):
        return "Auto injection."

    def execute_workflow_step(self, step, context):
        return WorkflowResult(step=step.step, success=True)
"""
        (mock_pkg / "plugin.py").write_text(plugin_code, encoding="utf-8")

        registry = PluginRegistry()
        count = registry.scan_directory(Path(temp_dir))
        assert count == 1
        assert "auto_draw" in registry.list_plugins()
        plugin = registry.get_plugin("auto_draw")
        assert plugin.version == "1.0.0"
    finally:
        shutil.rmtree(temp_dir)

def test_corrupted_plugin_fault_tolerance():
    """Verify that broken or invalid plugins are isolated without crashing valid ones."""
    temp_dir = tempfile.mkdtemp()
    try:
        # 1. Broken syntax plugin
        broken_pkg = Path(temp_dir) / "broken_plugin"
        broken_pkg.mkdir()
        (broken_pkg / "plugin.py").write_text("def broken syntax here !!@#$", encoding="utf-8")

        # 2. Valid plugin
        valid_pkg = Path(temp_dir) / "valid_plugin"
        valid_pkg.mkdir()
        (valid_pkg / "plugin.py").write_text("""
from atbmind_core.plugins.base import ATBMindPlugin
from atbmind_core.plugins.schemas import WorkflowResult

class ValidPlugin(ATBMindPlugin):
    @property
    def plugin_id(self) -> str:
        return "valid_plugin"
    @property
    def version(self) -> str:
        return "0.1.0"
    def initialize(self, config):
        pass
    def get_templates(self):
        return []
    def extract_context_entities(self, raw_input):
        return {}
    def get_domain_prompt_injection(self):
        return ""
    def execute_workflow_step(self, step, context):
        return WorkflowResult(step=step.step, success=True)
""", encoding="utf-8")

        registry = PluginRegistry()
        count = registry.scan_directory(Path(temp_dir))

        assert count == 1
        assert "valid_plugin" in registry.list_plugins()
        assert len(registry.failed_plugins) > 0
    finally:
        shutil.rmtree(temp_dir)

def test_entry_points_scan(monkeypatch):
    """Verify entry points discovery."""
    mock_entry_point = MagicMock()
    mock_entry_point.name = "ep_plugin"
    mock_entry_point.load.return_value = DummyPlugin

    def mock_entry_points(group=None):
        if group == "atbmind.plugins":
            return [mock_entry_point]
        return []

    monkeypatch.setattr("importlib.metadata.entry_points", mock_entry_points)

    registry = PluginRegistry()
    count = registry.scan_entry_points()
    assert count == 1
    assert "dummy" in registry.list_plugins()

def test_singleton_get_plugin_registry():
    """Verify get_plugin_registry singleton behavior."""
    r1 = get_plugin_registry(reset=True)
    r2 = get_plugin_registry(reset=False)
    assert r1 is r2

    r3 = get_plugin_registry(reset=True)
    assert r3 is not r1
