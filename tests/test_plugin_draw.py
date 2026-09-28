from pathlib import Path
from atbmind_core.plugins.registry import PluginRegistry
from atbmind_core.plugins.schemas import WorkflowStep, WorkflowResult
from plugins.draw.plugin import DrawPlugin
from plugins.draw.vision.extractor import DrawVisionExtractor
from plugins.draw.prompts.injection import get_draw_domain_prompt_injection


def test_draw_plugin_auto_discovery():
    """Verify PluginRegistry automatically discovers and registers DrawPlugin from plugins/ directory."""
    registry = PluginRegistry()
    count = registry.scan_directory("plugins")
    assert count >= 1
    assert "draw" in registry.list_plugins()

    plugin = registry.get_plugin("draw")
    assert plugin.plugin_id == "draw"
    assert plugin.version == "1.0.0"


def test_draw_vision_entity_and_mask_extraction(tmp_path: Path):
    """Verify DrawVisionExtractor and DrawPlugin extract entities, bbox, and masks from image input."""
    fake_img = tmp_path / "portrait_sample.jpg"
    fake_img.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01")

    plugin = DrawPlugin()
    plugin.initialize({})

    ctx = plugin.extract_context_entities(str(fake_img))
    assert "entities" in ctx
    assert len(ctx["entities"]) >= 1
    primary = ctx["entities"][0]
    assert primary["id"] == "person_0"
    assert "bbox" in primary
    assert len(primary["bbox"]) == 4

    assert "masks" in ctx
    masks = ctx["masks"]
    assert "face_mask" in masks
    assert "body_mask" in masks
    assert "clothing_mask" in masks
    assert "background_mask" in masks

    assert "scene_analysis" in ctx
    assert ctx["scene_analysis"]["source_name"] == "portrait_sample.jpg"


def test_draw_domain_prompt_injection():
    """Verify domain prompt injection contains portrait retouching latent intent rules."""
    plugin = DrawPlugin()
    prompt = plugin.get_domain_prompt_injection()
    assert prompt == get_draw_domain_prompt_injection()
    assert "clothing_protection" in prompt or "服装" in prompt
    assert "skin" in prompt.lower() or "肤质" in prompt
    assert "intensity" in prompt


def test_draw_plugin_templates_and_step_execution():
    """Verify DrawPlugin returns valid templates and executes workflow steps."""
    plugin = DrawPlugin()
    plugin.initialize({})

    templates = plugin.get_templates()
    assert len(templates) >= 3
    template_ids = {t.template_id for t in templates}
    assert "T_DRAW_BODY_SLIM" in template_ids
    assert "T_DRAW_CLOTH_PROTECT" in template_ids

    step = WorkflowStep(
        step=1,
        template_id="T_DRAW_BODY_SLIM",
        name="智能瘦身塑形",
        slots={"intensity": 0.15, "preserve_background": True},
    )
    res = plugin.execute_workflow_step(step, context={"input_image": "portrait.jpg"})
    assert isinstance(res, WorkflowResult)
    assert res.success is True
    assert res.step == 1
    assert res.output_data["template_id"] == "T_DRAW_BODY_SLIM"
    assert res.output_data["applied_slots"]["intensity"] == 0.15
