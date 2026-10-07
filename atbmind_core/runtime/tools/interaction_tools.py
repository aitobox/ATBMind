"""
Antigravity-Grade Interactive Question Modal and User Confirmation Toolset.
Implements AskQuestionTool (ask_question) for interactive disambiguation, user preferences,
and multiple-choice selections in PySide6 / Desktop environments.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

from atbmind_core.harness.tools.base import AgentTool, ExecutionMode, ToolResult
from atbmind_core.runtime.event_bus import AsyncEventBus, AskQuestionEvent

logger = logging.getLogger(__name__)


class QuestionSpec(BaseModel):
    """Specification for an interactive question presented to the user."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    question: str = Field(..., description="The question to ask the user.")
    options: List[str] = Field(..., description="The selectable options formatted as user responses.")
    is_multi_select: bool = Field(False, description="Whether multiple options can be selected.")

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data: Any) -> Any:
        if isinstance(data, dict):
            d = dict(data)
            if "isMultiSelect" in d and "is_multi_select" not in d:
                d["is_multi_select"] = d["isMultiSelect"]
            return d
        return data


class AskQuestionInput(BaseModel):
    """Input parameters for ask_question tool adhering to Antigravity specification."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    questions: List[QuestionSpec] = Field(..., description="The list of questions to ask.")
    toolAction: Optional[str] = Field(None, description="Brief 2-5 word phrase describing the action.")
    toolSummary: Optional[str] = Field(None, description="Brief 2-5 word noun phrase describing the task.")

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data: Any) -> Any:
        if isinstance(data, dict):
            d = dict(data)
            if "tool_action" in d and "toolAction" not in d:
                d["toolAction"] = d["tool_action"]
            if "tool_summary" in d and "toolSummary" not in d:
                d["toolSummary"] = d["tool_summary"]
            return d
        return data


class AskQuestionTool(AgentTool):
    """
    Use this tool to ask the user one or more multiple-choice questions, with the goal of:
    - Clarifying underspecified requirements
    - Soliciting design feedback or user preferences
    - Addressing ambiguous user intent
    - Picking a solution from a list of options

    Renders an interactive modal containing questions and selectable options in desktop UI,
    suspending execution until the user responds, or applying sensible defaults if no UI is attached.
    """

    name = "ask_question"
    description = (
        "Use this tool to ask the user one or more multiple-choice questions, with the goal of:\n"
        "- Clarifying underspecified requirements\n"
        "- Soliciting design feedback or user preferences\n"
        "- Addressing ambiguous user intent\n"
        "- Picking a solution from a list of options"
    )
    parameters_schema = AskQuestionInput
    execution_mode = ExecutionMode.SEQUENTIAL

    def __init__(
        self,
        event_bus: Optional[AsyncEventBus] = None,
        handler: Optional[Callable[..., Any]] = None,
        timeout: Optional[float] = None,
        mock_response: Optional[Any] = None,
    ) -> None:
        self.event_bus = event_bus
        self.handler = handler
        self.timeout = timeout
        self.mock_response = mock_response

    def set_handler(self, handler: Callable[..., Any]) -> None:
        """Register a custom callback or bridge handler for answering questions."""
        self.handler = handler

    def set_event_bus(self, event_bus: AsyncEventBus) -> None:
        """Attach an AsyncEventBus instance for dispatching AskQuestionEvent."""
        self.event_bus = event_bus

    async def execute(self, args: Dict[str, Any], context: Optional[Any] = None) -> ToolResult:
        """Executes ask_question, either awaiting UI response or falling back cleanly."""
        try:
            validated = self.parameters_schema.model_validate(args)
        except Exception as e:
            return ToolResult(
                content=f"Invalid arguments for ask_question: {e}",
                is_error=True,
            )

        questions_payload = [q.model_dump() for q in validated.questions]
        metadata_payload = {
            "questions": questions_payload,
            "toolAction": validated.toolAction or "",
            "toolSummary": validated.toolSummary or "",
        }

        # 1. Preset mock response
        if self.mock_response is not None:
            content = (
                json.dumps(self.mock_response, ensure_ascii=False)
                if isinstance(self.mock_response, (dict, list))
                else str(self.mock_response)
            )
            return ToolResult(
                content=content,
                metadata={"answers": self.mock_response, "mock": True},
            )

        # 2. Configured custom handler
        handler = self.handler or (getattr(context, "question_handler", None) if context else None)
        if handler is not None:
            loop = asyncio.get_running_loop()
            future: asyncio.Future = loop.create_future()
            try:
                sig = inspect.signature(handler)
                param_count = len(sig.parameters)
            except Exception:
                param_count = 2

            try:
                if param_count >= 2:
                    call_res = handler(metadata_payload, future)
                    if inspect.isawaitable(call_res):
                        await call_res
                    if self.timeout is not None:
                        response = await asyncio.wait_for(future, timeout=self.timeout)
                    else:
                        response = await future
                else:
                    call_res = handler(metadata_payload)
                    if inspect.isawaitable(call_res):
                        response = await call_res
                    else:
                        response = call_res

                content = (
                    json.dumps(response, ensure_ascii=False)
                    if isinstance(response, (dict, list))
                    else str(response)
                )
                return ToolResult(
                    content=content,
                    metadata={"answers": response, "questions": questions_payload},
                )
            except asyncio.TimeoutError:
                return ToolResult(
                    content=f"ask_question timed out after {self.timeout}s waiting for user response.",
                    is_error=True,
                )
            except asyncio.CancelledError:
                return ToolResult(
                    content="ask_question was cancelled.",
                    is_error=True,
                )
            except Exception as exc:
                return ToolResult(
                    content=f"Error executing question handler: {exc}",
                    is_error=True,
                )

        # 3. Configured AsyncEventBus
        bus = self.event_bus or (getattr(context, "event_bus", None) if context else None)
        if bus is not None:
            loop = asyncio.get_running_loop()
            future: asyncio.Future = loop.create_future()
            event = AskQuestionEvent(
                source_id="ask_question",
                questions=questions_payload,
                future=future,
                response_future=future,
                tool_action=validated.toolAction or "",
                tool_summary=validated.toolSummary or "",
            )

            await bus.publish(event)

            try:
                if self.timeout is not None:
                    response = await asyncio.wait_for(future, timeout=self.timeout)
                else:
                    response = await future

                content = (
                    json.dumps(response, ensure_ascii=False)
                    if isinstance(response, (dict, list))
                    else str(response)
                )
                return ToolResult(
                    content=content,
                    metadata={"answers": response, "questions": questions_payload},
                )
            except asyncio.TimeoutError:
                return ToolResult(
                    content=f"ask_question timed out after {self.timeout}s waiting for user response.",
                    is_error=True,
                )
            except asyncio.CancelledError:
                return ToolResult(
                    content="ask_question was cancelled.",
                    is_error=True,
                )
            except Exception as exc:
                return ToolResult(
                    content=f"Error waiting for question response: {exc}",
                    is_error=True,
                )

        # 4. Fallback mode: No handler or event bus configured
        fallback_answers: Dict[str, Any] = {}
        fallback_summary: List[str] = []
        for idx, q in enumerate(validated.questions):
            key = f"question_{idx + 1}"
            selected = q.options[0] if q.options else "Confirmed"
            fallback_answers[key] = selected
            fallback_summary.append(f"{q.question}: {selected}")

        content = (
            "No interactive UI handler configured. Defaulted to recommended choices:\n"
            + "\n".join(f"- {item}" for item in fallback_summary)
        )
        return ToolResult(
            content=content,
            metadata={
                "answers": fallback_answers,
                "fallback": True,
                "questions": questions_payload,
            },
        )
