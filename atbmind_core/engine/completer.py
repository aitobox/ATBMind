"""
ATBMind Layer 1: Latent Intent Completer Engine
Transforms colloquial, ambiguous user input into structured, canonical intent specifications.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from atbmind_core.config import get_config
from atbmind_core.engine.llm_client import OpenAICompatClient
from atbmind_core.plugins.base import ATBMindPlugin
from atbmind_core.plugins.schemas import StructuredIntentDraft

logger = logging.getLogger("atbmind.engine.completer")

class IntentCompleter:
    """
    Layer 1 engine responsible for latent intent completion and disambiguation.
    Combines raw user colloquial text with plugin-extracted context entities and domain rules.
    """

    def __init__(self, llm_client: Optional[OpenAICompatClient] = None) -> None:
        if llm_client is None:
            config = get_config()
            self.llm_client = OpenAICompatClient.from_config(config)
        else:
            self.llm_client = llm_client

    def _build_system_prompt(
        self, plugin: ATBMindPlugin, context_entities: Optional[Dict[str, Any]]
    ) -> str:
        """Constructs system prompt injecting plugin domain knowledge and context entities."""
        domain_injection = plugin.get_domain_prompt_injection()
        context_str = json.dumps(context_entities or {}, ensure_ascii=False)

        prompt = f"""You are the ATBMind Latent Intent Completion Engine (Layer 1) for plugin '{plugin.plugin_id}' (version {plugin.version}).
Your mission is to bridge low-bandwidth, ambiguous user colloquial requests into precise, structured domain intent drafts.

[Domain Rules & Commonsense Guidelines]
{domain_injection}

[Extracted Context Entities]
{context_str}

[Output Requirements]
You MUST respond with a JSON object conforming to the StructuredIntentDraft schema:
- "request_id": string (the provided request ID)
- "plugin_id": "{plugin.plugin_id}"
- "intent_category": string (e.g. body_shaping, face_detail, background_edit, etc.)
- "target_entities": list of objects referencing the detected context entities targeted by the action
- "parameters": object containing explicit and commonsense-imputed parameter values and intensities
- "plugin_payload": optional object for plugin-specific metadata (e.g. lock flags)
"""
        return prompt

    def complete_intent(
        self,
        user_prompt: str,
        plugin: ATBMindPlugin,
        context_entities: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> StructuredIntentDraft:
        """
        Synchronously completes ambiguous intent into StructuredIntentDraft.

        Args:
            user_prompt: Colloquial user command (e.g., '把这个人变瘦一点').
            plugin: Target domain plugin instance.
            context_entities: Entities extracted from inputs by plugin.
            request_id: Optional request identifier.

        Returns:
            StructuredIntentDraft: Validated intent draft model.
        """
        req_id = request_id or f"req-{uuid.uuid4().hex[:10]}"
        system_prompt = self._build_system_prompt(plugin, context_entities)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Request ID: {req_id}\nUser Command: {user_prompt}"},
        ]

        try:
            draft = self.llm_client.generate_structured_json(
                messages=messages,
                schema=StructuredIntentDraft,
            )
            # Ensure request_id and plugin_id consistency
            if not draft.request_id:
                draft.request_id = req_id
            draft.plugin_id = plugin.plugin_id
            return draft
        except Exception as e:
            logger.warning(
                "IntentCompleter LLM processing failed (%s). Generating heuristic fallback draft.",
                e,
            )
            entities = []
            if context_entities and "entities" in context_entities:
                entities = context_entities["entities"]
            elif context_entities and "detected_entities" in context_entities:
                entities = context_entities["detected_entities"]

            return StructuredIntentDraft(
                request_id=req_id,
                plugin_id=plugin.plugin_id,
                intent_category="general",
                target_entities=entities,
                parameters={"raw_prompt": user_prompt, "fallback": True},
            )

    async def acomplete_intent(
        self,
        user_prompt: str,
        plugin: ATBMindPlugin,
        context_entities: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> StructuredIntentDraft:
        """
        Asynchronously completes ambiguous intent into StructuredIntentDraft.
        """
        req_id = request_id or f"req-{uuid.uuid4().hex[:10]}"
        system_prompt = self._build_system_prompt(plugin, context_entities)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Request ID: {req_id}\nUser Command: {user_prompt}"},
        ]

        try:
            draft = await self.llm_client.agenerate_structured_json(
                messages=messages,
                schema=StructuredIntentDraft,
            )
            if not draft.request_id:
                draft.request_id = req_id
            draft.plugin_id = plugin.plugin_id
            return draft
        except Exception as e:
            logger.warning(
                "IntentCompleter async LLM processing failed (%s). Generating heuristic fallback draft.",
                e,
            )
            entities = []
            if context_entities and "entities" in context_entities:
                entities = context_entities["entities"]
            elif context_entities and "detected_entities" in context_entities:
                entities = context_entities["detected_entities"]

            return StructuredIntentDraft(
                request_id=req_id,
                plugin_id=plugin.plugin_id,
                intent_category="general",
                target_entities=entities,
                parameters={"raw_prompt": user_prompt, "fallback": True},
            )
