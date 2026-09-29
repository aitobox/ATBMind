import pytest
from typing import Any, Dict, List
from pydantic import ValidationError

from atbmind_core.plugins.schemas import (
    TemplateMetadata,
    StructuredIntentDraft,
    WorkflowStep,
    WorkflowResult,
)
from atbmind_core.plugins.base import ATBMindPlugin
from atbmind_core.plugins.exceptions import (
    ATBMindPluginError,
    PluginNotFoundError,
    PluginLoadError,
    PluginExecutionError,
    PluginValidationError,
)

def test_template_metadata_schema():
    """Verify TemplateMetadata validation, defaults, and serialization."""
    template = TemplateMetadata(
        template_id="T_DRAW_0101",
        name="Portrait Slimming",
        category="body_shaping",
        keywords=["slim", "waist", "portrait"],
        target_scope="single_person",
        slot_definitions={"strength": {"type": "float", "default": 0.15}},
        dependencies=[],
    )
    assert template.template_id == "T_DRAW_0101"
    assert template.name == "Portrait Slimming"
    assert template.category == "body_shaping"
    assert template.target_scope == "single_person"
    assert "strength" in template.slot_definitions
    assert template.dependencies == []

    # Verify missing required field triggers ValidationError
    with pytest.raises(ValidationError):
        TemplateMetadata(name="Incomplete")

def test_structured_intent_draft_schema():
    """Verify StructuredIntentDraft representation and optional payload."""
    draft = StructuredIntentDraft(
        request_id="req-12345",
        plugin_id="draw",
        intent_category="portrait_beautify",
        target_entities=[{"type": "person", "index": 0}],
        parameters={"intensity": 0.2},
        plugin_payload={"mask_detected": True},
    )
    assert draft.request_id == "req-12345"
    assert draft.plugin_id == "draw"
    assert len(draft.target_entities) == 1
    assert draft.plugin_payload == {"mask_detected": True}

def test_workflow_step_and_result():
    """Verify WorkflowStep and WorkflowResult contracts."""
    step = WorkflowStep(
        step=1,
        template_id="T_DRAW_0101",
        name="Apply Slimming",
        slots={"intensity": 0.15},
    )
    assert step.step == 1
    assert step.template_id == "T_DRAW_0101"
    assert step.slots == {"intensity": 0.15}

    result = WorkflowResult(
        step=1,
        success=True,
        output_data={"image_url": "https://example.com/out.png"},
        execution_time_ms=12.5,
    )
    assert result.step == 1
    assert result.success is True
    assert result.output_data["image_url"] == "https://example.com/out.png"
    assert result.execution_time_ms == 12.5
    assert result.error_message is None

def test_plugin_abstract_enforcement():
    """Verify that instantiating an incomplete subclass of ATBMindPlugin raises TypeError."""
    class IncompletePlugin(ATBMindPlugin):
        @property
        def plugin_id(self) -> str:
            return "incomplete"

    with pytest.raises(TypeError):
        IncompletePlugin()

def test_concrete_plugin_implementation():
    """Verify a complete concrete subclass implements all SPI methods cleanly."""
    class MockDrawPlugin(ATBMindPlugin):
        @property
        def plugin_id(self) -> str:
            return "mock_draw"

        @property
        def version(self) -> str:
            return "1.0.0"

        def initialize(self, config: Dict[str, Any]) -> None:
            self._initialized = True

        def get_templates(self) -> List[TemplateMetadata]:
            return [
                TemplateMetadata(
                    template_id="T_TEST_01",
                    name="Test Template",
                    category="test",
                    target_scope="global",
                )
            ]

        def extract_context_entities(self, raw_input: Any) -> Dict[str, Any]:
            return {"entities": ["subject"]}

        def get_domain_prompt_injection(self) -> str:
            return "Domain knowledge rules."

        def execute_workflow_step(self, step: WorkflowStep, context: Dict[str, Any]) -> WorkflowResult:
            return WorkflowResult(
                step=step.step,
                success=True,
                output_data={"status": "done"},
                execution_time_ms=5.0,
            )

    plugin = MockDrawPlugin()
    assert plugin.plugin_id == "mock_draw"
    assert plugin.version == "1.0.0"
    plugin.initialize({})
    assert plugin._initialized is True
    templates = plugin.get_templates()
    assert len(templates) == 1
    assert templates[0].template_id == "T_TEST_01"
    entities = plugin.extract_context_entities("image.jpg")
    assert entities == {"entities": ["subject"]}
    assert "Domain knowledge" in plugin.get_domain_prompt_injection()
    res = plugin.execute_workflow_step(
        WorkflowStep(step=1, template_id="T_TEST_01", name="Step1"), {}
    )
    assert res.success is True

def test_plugin_exceptions_hierarchy():
    """Verify custom exception inheritance and behavior."""
    assert issubclass(PluginNotFoundError, ATBMindPluginError)
    assert issubclass(PluginLoadError, ATBMindPluginError)
    assert issubclass(PluginExecutionError, ATBMindPluginError)
    assert issubclass(PluginValidationError, ATBMindPluginError)

    err = PluginNotFoundError("Plugin 'abc' not found")
    assert str(err) == "Plugin 'abc' not found"
    assert isinstance(err, ATBMindPluginError)


def test_plugin_ui_spec_schema_and_base_default():
    """Verify PluginUISpec validation, defaults, JSON/dict serialization, and ATBMindPlugin.get_ui_spec() default."""
    from atbmind_core.plugins.schemas import PluginUISpec

    spec = PluginUISpec(
        plugin_id="draw",
        display_name="图像生成 (ATBDraw)",
        icon="🖼️",
        models=["Seedream 4.5", "Flux.1"],
        aspect_ratios=["自动", "1:1", "16:9"],
        styles=[{"id": "portrait", "name": "人像摄影", "icon": "📷"}],
        templates=[
            TemplateMetadata(
                template_id="T_DRAW_01",
                name="智能全身自然显瘦塑形",
                category="body_shaping",
                target_scope="single_person",
            )
        ],
    )
    assert spec.plugin_id == "draw"
    assert spec.display_name == "图像生成 (ATBDraw)"
    assert spec.icon == "🖼️"
    assert spec.supports_attachments is True
    assert spec.attachment_types == [".png", ".jpg", ".jpeg", ".webp"]
    assert "Seedream 4.5" in spec.models
    assert "1:1" in spec.aspect_ratios
    assert spec.styles[0]["name"] == "人像摄影"
    assert len(spec.templates) == 1

    dumped = spec.model_dump()
    assert dumped["plugin_id"] == "draw"
    assert dumped["supports_attachments"] is True
    json_str = spec.model_dump_json()
    restored = PluginUISpec.model_validate_json(json_str)
    assert restored == spec

    class MinimalPlugin(ATBMindPlugin):
        @property
        def plugin_id(self) -> str:
            return "minimal"

        @property
        def version(self) -> str:
            return "0.1.0"

        def initialize(self, config: Dict[str, Any]) -> None:
            pass

        def get_templates(self) -> List[TemplateMetadata]:
            return []

        def extract_context_entities(self, raw_input: Any) -> Dict[str, Any]:
            return {}

        def get_domain_prompt_injection(self) -> str:
            return ""

        def execute_workflow_step(self, step: WorkflowStep, context: Dict[str, Any]) -> WorkflowResult:
            return WorkflowResult(step=step.step, success=True)

    p = MinimalPlugin()
    assert p.get_ui_spec() is None

