import json
import asyncio
import pytest
import httpx
from typing import Any, Dict, List

from atbmind_core.engine.completer import IntentCompleter
from atbmind_core.engine.llm_client import OpenAICompatClient
from atbmind_core.plugins.base import ATBMindPlugin
from atbmind_core.plugins.schemas import TemplateMetadata, WorkflowStep, WorkflowResult, StructuredIntentDraft

class MockDrawPlugin(ATBMindPlugin):
    @property
    def plugin_id(self) -> str:
        return "draw"

    @property
    def version(self) -> str:
        return "1.0.0"

    def initialize(self, config: Dict[str, Any]) -> None:
        pass

    def get_templates(self) -> List[TemplateMetadata]:
        return []

    def extract_context_entities(self, raw_input: Any) -> Dict[str, Any]:
        return {"detected_entities": [{"id": "person_0", "label": "person", "bbox": [10, 20, 100, 200]}]}

    def get_domain_prompt_injection(self) -> str:
        return "Rule 1: Portrait slimming should default to 12% intensity with clothing deformation lock."

    def execute_workflow_step(self, step: WorkflowStep, context: Dict[str, Any]) -> WorkflowResult:
        return WorkflowResult(step=step.step, success=True)

def test_intent_completer_basic():
    """Verify basic colloquial intent expansion into StructuredIntentDraft."""
    def handler(request: httpx.Request) -> httpx.Response:
        data = json.loads(request.content.decode("utf-8"))
        # Verify prompt injection was passed in system prompt
        sys_msg = data["messages"][0]["content"]
        assert "Rule 1: Portrait slimming" in sys_msg
        assert "person_0" in sys_msg

        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({
                                "request_id": "req-999",
                                "plugin_id": "draw",
                                "intent_category": "body_shaping",
                                "target_entities": [{"id": "person_0", "label": "person"}],
                                "parameters": {"slimming_intensity": 0.12, "protect_clothing": True},
                                "plugin_payload": {"lock_mask": True},
                            })
                        }
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    llm = OpenAICompatClient(transport=transport)
    completer = IntentCompleter(llm_client=llm)
    plugin = MockDrawPlugin()

    draft = completer.complete_intent(
        user_prompt="把右边的人稍微变瘦一点",
        plugin=plugin,
        context_entities={"entities": [{"id": "person_0"}]},
        request_id="req-999",
    )

    assert isinstance(draft, StructuredIntentDraft)
    assert draft.request_id == "req-999"
    assert draft.plugin_id == "draw"
    assert draft.intent_category == "body_shaping"
    assert draft.parameters["slimming_intensity"] == 0.12
    assert draft.parameters["protect_clothing"] is True
    assert draft.target_entities[0]["id"] == "person_0"

def test_async_intent_completion():
    """Verify asynchronous complete_intent works identically."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({
                                "request_id": "req-async",
                                "plugin_id": "draw",
                                "intent_category": "face_detail",
                                "target_entities": [],
                                "parameters": {"jawline_strength": 0.2},
                            })
                        }
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    llm = OpenAICompatClient(transport=transport)
    completer = IntentCompleter(llm_client=llm)
    plugin = MockDrawPlugin()

    draft = asyncio.run(
        completer.acomplete_intent(
            user_prompt="下巴弄尖一点",
            plugin=plugin,
            request_id="req-async",
        )
    )

    assert draft.request_id == "req-async"
    assert draft.intent_category == "face_detail"
    assert draft.parameters["jawline_strength"] == 0.2

def test_fallback_on_corrupted_llm_response():
    """Verify fallback draft generation if LLM returns malformed content."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "not json at all"}}]})

    transport = httpx.MockTransport(handler)
    llm = OpenAICompatClient(transport=transport)
    completer = IntentCompleter(llm_client=llm)
    plugin = MockDrawPlugin()

    draft = completer.complete_intent(
        user_prompt="瘦一点",
        plugin=plugin,
        context_entities={"entities": [{"id": "person_0"}]},
        request_id="req-fallback",
    )

    assert isinstance(draft, StructuredIntentDraft)
    assert draft.request_id == "req-fallback"
    assert draft.plugin_id == "draw"
    assert draft.intent_category == "general"
    assert draft.parameters.get("raw_prompt") == "瘦一点"
