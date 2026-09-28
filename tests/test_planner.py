import json
import asyncio
import pytest
import httpx

from atbmind_core.engine.planner import WorkflowPlanner
from atbmind_core.engine.llm_client import OpenAICompatClient
from atbmind_core.plugins.schemas import (
    TemplateMetadata,
    StructuredIntentDraft,
    WorkflowPlan,
)
from atbmind_core.plugins.exceptions import CyclicDependencyError

@pytest.fixture
def sample_templates():
    return [
        TemplateMetadata(
            template_id="T_SHAPE_001",
            name="Body Slimming",
            category="body_shaping",
            keywords=["slim", "waist"],
            target_scope="single_person",
            slot_definitions={"intensity": {"type": "float", "default": 0.12}},
            dependencies=[],
        ),
        TemplateMetadata(
            template_id="T_CLOTH_002",
            name="Clothing Anti-Distortion",
            category="body_shaping",
            keywords=["clothing", "wrinkle"],
            target_scope="single_person",
            slot_definitions={"preserve_ratio": {"type": "float", "default": 0.85}},
            dependencies=["T_SHAPE_001"],
        ),
        TemplateMetadata(
            template_id="T_BG_003",
            name="Background Lock",
            category="body_shaping",
            keywords=["background", "lock"],
            target_scope="background",
            slot_definitions={"feather": {"type": "int", "default": 5}},
            dependencies=["T_CLOTH_002"],
        ),
    ]

@pytest.fixture
def sample_draft():
    return StructuredIntentDraft(
        request_id="req-plan-1",
        plugin_id="draw",
        intent_category="body_shaping",
        target_entities=[{"id": "person_0"}],
        parameters={"intensity": 0.15},
    )

def test_anti_hallucination_filtering(sample_templates, sample_draft):
    """Verify hallucinated template IDs not in library are dropped."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({
                                "selected_templates": ["T_FAKE_999", "T_SHAPE_001", "T_GHOST_123"]
                            })
                        }
                    }
                ]
            },
        )

    llm = OpenAICompatClient(transport=httpx.MockTransport(handler))
    planner = WorkflowPlanner(llm_client=llm)

    plan = planner.plan_workflow(sample_draft, sample_templates)
    assert isinstance(plan, WorkflowPlan)
    assert len(plan.steps) == 1
    assert plan.steps[0].template_id == "T_SHAPE_001"
    assert plan.steps[0].step == 1

def test_topological_sort_order_correction(sample_templates, sample_draft):
    """Verify inverted dependency order from LLM is corrected by topological sort."""
    def handler(request: httpx.Request) -> httpx.Response:
        # LLM outputs reverse order: T_BG_003 -> T_CLOTH_002 -> T_SHAPE_001
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({
                                "selected_templates": ["T_BG_003", "T_CLOTH_002", "T_SHAPE_001"]
                            })
                        }
                    }
                ]
            },
        )

    llm = OpenAICompatClient(transport=httpx.MockTransport(handler))
    planner = WorkflowPlanner(llm_client=llm)

    plan = planner.plan_workflow(sample_draft, sample_templates)
    ordered_ids = [s.template_id for s in plan.steps]
    assert ordered_ids == ["T_SHAPE_001", "T_CLOTH_002", "T_BG_003"]
    assert [s.step for s in plan.steps] == [1, 2, 3]

def test_auto_dependency_expansion(sample_templates, sample_draft):
    """Verify selecting a dependent template automatically includes its prerequisite."""
    def handler(request: httpx.Request) -> httpx.Response:
        # LLM only selects T_BG_003, which transitively depends on T_CLOTH_002 and T_SHAPE_001
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({
                                "selected_templates": ["T_BG_003"]
                            })
                        }
                    }
                ]
            },
        )

    llm = OpenAICompatClient(transport=httpx.MockTransport(handler))
    planner = WorkflowPlanner(llm_client=llm)

    plan = planner.plan_workflow(sample_draft, sample_templates)
    ordered_ids = [s.template_id for s in plan.steps]
    assert ordered_ids == ["T_SHAPE_001", "T_CLOTH_002", "T_BG_003"]

def test_circular_dependency_detection(sample_draft):
    """Verify circular dependencies raise CyclicDependencyError."""
    cyclic_templates = [
        TemplateMetadata(
            template_id="T_A",
            name="A",
            category="body_shaping",
            target_scope="global",
            dependencies=["T_B"],
        ),
        TemplateMetadata(
            template_id="T_B",
            name="B",
            category="body_shaping",
            target_scope="global",
            dependencies=["T_A"],
        ),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps({"selected_templates": ["T_A", "T_B"]})}}]},
        )

    llm = OpenAICompatClient(transport=httpx.MockTransport(handler))
    planner = WorkflowPlanner(llm_client=llm)

    with pytest.raises(CyclicDependencyError):
        planner.plan_workflow(sample_draft, cyclic_templates)

def test_async_plan_workflow(sample_templates, sample_draft):
    """Verify asynchronous workflow planning."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({
                                "selected_templates": ["T_CLOTH_002"]
                            })
                        }
                    }
                ]
            },
        )

    llm = OpenAICompatClient(transport=httpx.MockTransport(handler))
    planner = WorkflowPlanner(llm_client=llm)

    plan = asyncio.run(planner.aplan_workflow(sample_draft, sample_templates))
    assert [s.template_id for s in plan.steps] == ["T_SHAPE_001", "T_CLOTH_002"]
