from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from atbmind_core.plugins.base import ATBMindPlugin
from atbmind_core.plugins.schemas import (
    StructuredIntentDraft,
    TemplateMetadata,
    WorkflowExecutionReport,
    WorkflowPlan,
    WorkflowResult,
    WorkflowStep,
)

logger = logging.getLogger(__name__)


class SlotDispatcher:
    """
    Layer 3: Universal Slot Filling and Workflow Execution Dispatcher.
    Resolves parameter slot hierarchy (defaults -> planner slots -> draft parameters -> user overrides)
    and dispatches topologically sorted workflow steps to the active ATBMindPlugin.
    """

    def fill_slots(
        self,
        step: WorkflowStep,
        template: Optional[TemplateMetadata] = None,
        draft: Optional[StructuredIntentDraft] = None,
        user_overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Resolve slot values according to priority:
        1. Template default value (`template.slot_definitions[name]["default"]`)
        2. Step bound slots (`step.slots`)
        3. Draft extracted parameters (`draft.parameters`)
        4. User manual overrides from side drawer (`user_overrides`)
        """
        filled: Dict[str, Any] = {}
        slot_defs = template.slot_definitions if template and template.slot_definitions else {}
        step_slots = step.slots or {}
        draft_params = draft.parameters if draft and draft.parameters else {}
        overrides = user_overrides or {}

        # 1. Initialize from template definitions
        for slot_name, meta in slot_defs.items():
            slot_type = "string"
            default_val = None
            if isinstance(meta, dict):
                slot_type = meta.get("type", "string")
                default_val = meta.get("default")
            else:
                default_val = meta

            val = default_val
            if slot_name in step_slots and step_slots[slot_name] is not None:
                val = step_slots[slot_name]
            if slot_name in draft_params and draft_params[slot_name] is not None:
                val = draft_params[slot_name]
            if slot_name in overrides and overrides[slot_name] is not None:
                val = overrides[slot_name]

            if val is not None:
                val = self._coerce_type(val, slot_type)
            filled[slot_name] = val

        # 2. Carry over extra parameters not explicitly in slot_definitions
        for source in (step_slots, draft_params, overrides):
            for k, v in source.items():
                if k not in filled and v is not None:
                    filled[k] = v

        # 3. Inject target entities if present on draft and not overridden
        if draft and draft.target_entities and "target_entities" not in filled:
            filled["target_entities"] = draft.target_entities

        return filled

    def _coerce_type(self, value: Any, slot_type: str) -> Any:
        st = str(slot_type or "string").lower()
        try:
            if st in ("float", "number"):
                return float(value)
            if st in ("int", "integer"):
                return int(float(value))
            if st in ("bool", "boolean"):
                if isinstance(value, str):
                    return value.strip().lower() in ("true", "1", "yes", "on")
                return bool(value)
            if st in ("str", "string"):
                return str(value)
        except (ValueError, TypeError):
            logger.warning("Failed to coerce slot value %r to %s, keeping raw value", value, slot_type)
        return value

    def dispatch_workflow(
        self,
        plan: WorkflowPlan,
        plugin: ATBMindPlugin,
        draft: Optional[StructuredIntentDraft] = None,
        initial_context: Optional[Dict[str, Any]] = None,
        user_overrides: Optional[Dict[str, Any]] = None,
        stop_on_error: bool = True,
    ) -> WorkflowExecutionReport:
        """
        Execute all steps in `plan` sequentially through `plugin.execute_workflow_step()`,
        chaining intermediate outputs via `context["previous_output"]`.
        """
        templates = plugin.get_templates() or []
        template_map: Dict[str, TemplateMetadata] = {t.template_id: t for t in templates}

        context: Dict[str, Any] = dict(initial_context or {})
        if draft and draft.plugin_payload:
            context.setdefault("plugin_payload", draft.plugin_payload)

        step_results: List[WorkflowResult] = []
        executed_steps: List[WorkflowStep] = []
        overall_success = True
        total_time_ms = 0.0
        final_output: Dict[str, Any] = {}

        for step in plan.steps:
            template = template_map.get(step.template_id)
            filled_slots = self.fill_slots(
                step=step,
                template=template,
                draft=draft,
                user_overrides=user_overrides,
            )
            bound_step = step.model_copy(update={"slots": filled_slots})
            executed_steps.append(bound_step)

            start_t = time.perf_counter()
            try:
                res = plugin.execute_workflow_step(bound_step, dict(context))
            except Exception as exc:
                elapsed_ms = (time.perf_counter() - start_t) * 1000.0
                logger.error("Step %s (%s) raised exception: %s", step.step, step.template_id, exc)
                res = WorkflowResult(
                    step=step.step,
                    success=False,
                    output_data={},
                    execution_time_ms=elapsed_ms,
                    error_message=str(exc),
                )

            step_results.append(res)
            total_time_ms += res.execution_time_ms

            if not res.success:
                overall_success = False
                if stop_on_error:
                    break
            else:
                context["previous_output"] = res.output_data
                context[f"step_{step.step}_output"] = res.output_data
                final_output = res.output_data

        return WorkflowExecutionReport(
            request_id=plan.request_id,
            plugin_id=plan.plugin_id,
            success=overall_success,
            total_execution_time_ms=total_time_ms,
            step_results=step_results,
            executed_steps=executed_steps,
            final_output=final_output,
        )
