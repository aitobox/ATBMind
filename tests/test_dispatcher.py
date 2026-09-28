import pytest
from typing import Any, Dict, List

from atbmind_core.engine.dispatcher import SlotDispatcher
from atbmind_core.plugins.base import ATBMindPlugin
from atbmind_core.plugins.schemas import (
    TemplateMetadata,
    StructuredIntentDraft,
    WorkflowStep,
    WorkflowPlan,
    WorkflowResult,
    WorkflowExecutionReport,
)

class MockExecutionPlugin(ATBMindPlugin):
    def __init__(self, fail_on_step: int | None = None):
        self.fail_on_step = fail_on_step
        self.received_steps: List[WorkflowStep] = []
        self.received_contexts: List[Dict[str, Any]] = []

    @property
    def plugin_id(self) -> str:
        return "draw"

    @property
    def version(self) -> str:
        return "1.0.0"

    def initialize(self, config: Dict[str, Any]) -> None:
        pass

    def get_templates(self) -> List[TemplateMetadata]:
        return [
            TemplateMetadata(
                template_id="T_SHAPE_001",
                name="Body Slimming",
                category="body_shaping",
                target_scope="single_person",
                slot_definitions={
                    "intensity": {"type": "float", "default": 0.12},
                    "smoothness": {"type": "float", "default": 0.5},
                },
            ),
            TemplateMetadata(
                template_id="T_CLOTH_002",
                name="Clothing Protection",
                category="body_shaping",
                target_scope="single_person",
                slot_definitions={
                    "preserve_ratio": {"type": "float", "default": 0.85},
                },
                dependencies=["T_SHAPE_001"],
            ),
        ]

    def extract_context_entities(self, raw_input: Any) -> Dict[str, Any]:
        return {}

    def get_domain_prompt_injection(self) -> str:
        return ""

    def execute_workflow_step(self, step: WorkflowStep, context: Dict[str, Any]) -> WorkflowResult:
        self.received_steps.append(step)
        self.received_contexts.append(dict(context))

        if self.fail_on_step == step.step:
            raise RuntimeError(f"Simulated crash at step {step.step}")

        return WorkflowResult(
            step=step.step,
            success=True,
            output_data={
                "rendered_asset": f"asset_after_{step.template_id}.png",
                "applied_slots": step.slots,
            },
            execution_time_ms=10.0,
        )

def test_slot_filling_hierarchy_and_defaults():
    """Verify default fallbacks, draft overrides, and user side-drawer overrides."""
    dispatcher = SlotDispatcher()
    plugin = MockExecutionPlugin()
    template = plugin.get_templates()[0]  # T_SHAPE_001 (intensity default 0.12, smoothness default 0.5)

    step = WorkflowStep(step=1, template_id="T_SHAPE_001", name="Slim")
    draft = StructuredIntentDraft(
        request_id="r1",
        plugin_id="draw",
        intent_category="body_shaping",
        parameters={"intensity": 0.18},  # overrides default 0.12, leaves smoothness at 0.5
    )

    # 1. Draft + defaults
    filled = dispatcher.fill_slots(step, template, draft)
    assert filled["intensity"] == 0.18
    assert filled["smoothness"] == 0.5

    # 2. User side-drawer override takes highest priority
    filled_override = dispatcher.fill_slots(
        step, template, draft, user_overrides={"intensity": "0.25"}
    )
    assert filled_override["intensity"] == 0.25
    assert filled_override["smoothness"] == 0.5

def test_sequential_workflow_execution_and_context_chaining():
    """Verify full workflow dispatch, context chaining, and execution report."""
    dispatcher = SlotDispatcher()
    plugin = MockExecutionPlugin()

    plan = WorkflowPlan(
        request_id="req-exec-1",
        plugin_id="draw",
        steps=[
            WorkflowStep(step=1, template_id="T_SHAPE_001", name="Body Slimming"),
            WorkflowStep(step=2, template_id="T_CLOTH_002", name="Clothing Protection"),
        ],
    )
    draft = StructuredIntentDraft(
        request_id="req-exec-1",
        plugin_id="draw",
        intent_category="body_shaping",
        target_entities=[{"id": "person_0"}],
        parameters={"intensity": 0.16},
    )

    report = dispatcher.dispatch_workflow(
        plan=plan,
        plugin=plugin,
        draft=draft,
        initial_context={"input_image": "raw.png"},
    )

    assert isinstance(report, WorkflowExecutionReport)
    assert report.success is True
    assert len(report.step_results) == 2
    assert len(report.executed_steps) == 2

    # Verify step 1 slots
    assert report.executed_steps[0].slots["intensity"] == 0.16
    assert report.executed_steps[0].slots["smoothness"] == 0.5

    # Verify step 2 received step 1's output in context["previous_output"]
    step2_ctx = plugin.received_contexts[1]
    assert step2_ctx["previous_output"]["rendered_asset"] == "asset_after_T_SHAPE_001.png"

    # Verify final output
    assert report.final_output["rendered_asset"] == "asset_after_T_CLOTH_002.png"

def test_error_capture_and_graceful_stop():
    """Verify single-step exception is caught cleanly and halts subsequent steps when stop_on_error=True."""
    dispatcher = SlotDispatcher()
    plugin = MockExecutionPlugin(fail_on_step=1)

    plan = WorkflowPlan(
        request_id="req-fail",
        plugin_id="draw",
        steps=[
            WorkflowStep(step=1, template_id="T_SHAPE_001", name="Body Slimming"),
            WorkflowStep(step=2, template_id="T_CLOTH_002", name="Clothing Protection"),
        ],
    )

    report = dispatcher.dispatch_workflow(plan=plan, plugin=plugin, stop_on_error=True)
    assert report.success is False
    assert len(report.step_results) == 1
    assert report.step_results[0].success is False
    assert "Simulated crash at step 1" in report.step_results[0].error_message

def test_continue_on_error_option():
    """Verify stop_on_error=False continues executing remaining steps."""
    dispatcher = SlotDispatcher()
    plugin = MockExecutionPlugin(fail_on_step=1)

    plan = WorkflowPlan(
        request_id="req-cont",
        plugin_id="draw",
        steps=[
            WorkflowStep(step=1, template_id="T_SHAPE_001", name="Body Slimming"),
            WorkflowStep(step=2, template_id="T_CLOTH_002", name="Clothing Protection"),
        ],
    )

    report = dispatcher.dispatch_workflow(plan=plan, plugin=plugin, stop_on_error=False)
    assert report.success is False
    assert len(report.step_results) == 2
    assert report.step_results[0].success is False
    assert report.step_results[1].success is True
