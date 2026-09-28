"""
ATBMind Layer 2: Workflow Planner & Topological DAG Engine
Matches structured intent drafts against domain templates and enforces topological dependency ordering.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Set

from atbmind_core.config import get_config
from atbmind_core.engine.llm_client import OpenAICompatClient
from atbmind_core.plugins.exceptions import CyclicDependencyError
from atbmind_core.plugins.schemas import (
    StructuredIntentDraft,
    TemplateMetadata,
    WorkflowPlan,
    WorkflowStep,
)

logger = logging.getLogger("atbmind.engine.planner")

class WorkflowPlanner:
    """
    Layer 2 planner responsible for selecting candidate templates,
    preventing LLM hallucinations, expanding prerequisites, and performing DAG topological sorting.
    """

    def __init__(
        self,
        llm_client: Optional[OpenAICompatClient] = None,
        max_candidates: int = 200,
    ) -> None:
        if llm_client is None:
            config = get_config()
            self.llm_client = OpenAICompatClient.from_config(config)
        else:
            self.llm_client = llm_client
        self.max_candidates = max_candidates

    def _select_candidates(
        self, draft: StructuredIntentDraft, available_templates: List[TemplateMetadata]
    ) -> List[TemplateMetadata]:
        """Filters and prioritizes candidate templates by intent category and keyword overlap."""
        hint_tokens = set()
        raw_kws = draft.parameters.get("keywords") or draft.parameters.get("intent_keywords") or []
        if isinstance(raw_kws, list):
            for kw in raw_kws:
                hint_tokens.add(str(kw).lower())
        for val in draft.parameters.values():
            if isinstance(val, str):
                hint_tokens.add(val.lower())

        def _score(tpl: TemplateMetadata) -> tuple[int, int]:
            cat_match = 1 if tpl.category == draft.intent_category else 0
            kw_overlap = 0
            for kw in tpl.keywords:
                kw_low = kw.lower()
                if any(kw_low in h or h in kw_low for h in hint_tokens):
                    kw_overlap += 2
            if any(h in tpl.name.lower() for h in hint_tokens):
                kw_overlap += 3
            return (cat_match, kw_overlap)

        ranked = sorted(available_templates, key=_score, reverse=True)
        return ranked[: self.max_candidates]

    def _build_selection_messages(
        self, draft: StructuredIntentDraft, candidates: List[TemplateMetadata]
    ) -> List[Dict[str, str]]:
        """Builds system and user prompt for LLM template selection."""
        compressed = [
            {
                "template_id": t.template_id,
                "name": t.name,
                "category": t.category,
                "keywords": t.keywords,
                "dependencies": t.dependencies,
            }
            for t in candidates
        ]

        system_prompt = f"""You are the ATBMind Topological Workflow Planner (Layer 2).
Given a StructuredIntentDraft and a catalog of available domain templates, select the minimal, optimal set of templates to fulfill the user's intent.

[Available Templates Catalog]
{json.dumps(compressed, ensure_ascii=False)}

[Strict Rules]
1. You MUST ONLY select template IDs that exist in the Available Templates Catalog above. NEVER invent or hallucinate IDs.
2. Output valid JSON in the exact format:
   {{"selected_templates": ["TEMPLATE_ID_1", "TEMPLATE_ID_2"]}}
"""
        user_prompt = f"Structured Intent Draft:\n{draft.model_dump_json(indent=2)}"
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _resolve_and_sort_dag(
        self,
        raw_selected_ids: List[str],
        template_map: Dict[str, TemplateMetadata],
        draft: StructuredIntentDraft,
    ) -> List[WorkflowStep]:
        """
        1. Filters out hallucinated template IDs.
        2. Expands transitive dependencies.
        3. Performs DFS topological sort with cycle detection.
        4. Binds initial default/draft slots and returns ordered WorkflowSteps.
        """
        # 1. Anti-hallucination filter (preserve order, deduplicate)
        valid_initial: List[str] = []
        for tid in raw_selected_ids:
            if tid in template_map and tid not in valid_initial:
                valid_initial.append(tid)
            elif tid not in template_map:
                logger.warning("Dropped hallucinated template ID not in catalog: %s", tid)

        # 2. Expand transitive dependencies & 3. Topological sort with cycle detection
        # State: 0 = unvisited, 1 = visiting (active recursion stack), 2 = visited
        state: Dict[str, int] = {}
        sorted_ids: List[str] = []

        def dfs_visit(tid: str) -> None:
            current_state = state.get(tid, 0)
            if current_state == 1:
                raise CyclicDependencyError(
                    f"Circular dependency detected involving template '{tid}'"
                )
            if current_state == 2:
                return

            state[tid] = 1
            t_meta = template_map.get(tid)
            if t_meta:
                for dep_id in t_meta.dependencies:
                    if dep_id in template_map:
                        dfs_visit(dep_id)
            state[tid] = 2
            sorted_ids.append(tid)

        for root_id in valid_initial:
            dfs_visit(root_id)

        # 4. Build WorkflowStep list
        steps: List[WorkflowStep] = []
        for idx, tid in enumerate(sorted_ids, start=1):
            t_meta = template_map[tid]
            slots: Dict[str, Any] = {}
            for slot_name, slot_spec in t_meta.slot_definitions.items():
                if isinstance(slot_spec, dict) and "default" in slot_spec:
                    slots[slot_name] = slot_spec["default"]
                if slot_name in draft.parameters:
                    slots[slot_name] = draft.parameters[slot_name]

            steps.append(
                WorkflowStep(
                    step=idx,
                    template_id=tid,
                    name=t_meta.name,
                    slots=slots,
                )
            )

        return steps

    def plan_workflow(
        self,
        draft: StructuredIntentDraft,
        available_templates: List[TemplateMetadata],
    ) -> WorkflowPlan:
        """
        Synchronously plans and sorts the execution workflow for a given intent draft.
        """
        template_map = {t.template_id: t for t in available_templates}
        if not template_map:
            return WorkflowPlan(
                request_id=draft.request_id,
                plugin_id=draft.plugin_id,
                steps=[],
            )

        candidates = self._select_candidates(draft, available_templates)
        messages = self._build_selection_messages(draft, candidates)

        raw_selected: List[str] = []
        try:
            res = self.llm_client.generate_structured_json(messages=messages)
            if isinstance(res, dict) and isinstance(res.get("selected_templates"), list):
                raw_selected = [str(x) for x in res["selected_templates"]]
        except Exception as e:
            logger.warning("WorkflowPlanner LLM call failed (%s). Using category fallback.", e)
            if candidates:
                raw_selected = [candidates[0].template_id]

        steps = self._resolve_and_sort_dag(raw_selected, template_map, draft)
        return WorkflowPlan(
            request_id=draft.request_id,
            plugin_id=draft.plugin_id,
            steps=steps,
        )

    async def aplan_workflow(
        self,
        draft: StructuredIntentDraft,
        available_templates: List[TemplateMetadata],
    ) -> WorkflowPlan:
        """
        Asynchronously plans and sorts the execution workflow for a given intent draft.
        """
        template_map = {t.template_id: t for t in available_templates}
        if not template_map:
            return WorkflowPlan(
                request_id=draft.request_id,
                plugin_id=draft.plugin_id,
                steps=[],
            )

        candidates = self._select_candidates(draft, available_templates)
        messages = self._build_selection_messages(draft, candidates)

        raw_selected: List[str] = []
        try:
            res = await self.llm_client.agenerate_structured_json(messages=messages)
            if isinstance(res, dict) and isinstance(res.get("selected_templates"), list):
                raw_selected = [str(x) for x in res["selected_templates"]]
        except Exception as e:
            logger.warning("WorkflowPlanner async LLM call failed (%s). Using category fallback.", e)
            if candidates:
                raw_selected = [candidates[0].template_id]

        steps = self._resolve_and_sort_dag(raw_selected, template_map, draft)
        return WorkflowPlan(
            request_id=draft.request_id,
            plugin_id=draft.plugin_id,
            steps=steps,
        )
