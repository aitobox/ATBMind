"""
ATBMind Desktop Background Workers (QThread)
Implements GenerationWorker and TitleWorker for non-blocking multi-turn
portrait generation (Layer 1 -> Layer 2 -> Layer 3), plain-text chat, and
asynchronous first-turn conversation title summarization.
"""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path
from typing import Any, Dict, Optional
from PySide6.QtCore import QObject, QThread, Signal

from atbmind_core.config import AppConfig, get_config
from atbmind_core.engine.completer import IntentCompleter
from atbmind_core.engine.dispatcher import SlotDispatcher
from atbmind_core.engine.llm_client import OpenAICompatClient
from atbmind_core.engine.planner import WorkflowPlanner
from atbmind_core.plugins.base import ATBMindPlugin
from atbmind_core.plugins.schemas import WorkflowStep
from plugins.draw.plugin import DrawPlugin

logger = logging.getLogger("atbmind.desktop.workers")

# Minimal valid 1x1 PNG fallback bytes
_MINIMAL_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc`\xf8\xff"
    b"\xff?\x00\x05\xfe\x02\xfe\xa75\x81\x84\x00\x00\x00\x00IEND\xaeB`\x82"
)


class _OfflineFallbackLLMClient:
    """
    Fast local LLM stub used when no API key is configured in AppConfig
    and no custom llm_client is injected, avoiding 30s network timeouts in local/offline mode.
    """

    def chat_completion(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_msg = str(m.get("content", "")).strip()
                break
        return f"已收到您的请求：{user_msg}" if user_msg else "您好！我是 ATBMind 智能助手。"

    def generate_structured_json(self, messages: list[dict[str, str]], schema: Any = None, **kwargs: Any) -> Any:
        raise RuntimeError("Offline local mode: triggering fast heuristic engine fallback")


def _build_default_llm_client(config: AppConfig) -> Any:
    """Returns OpenAICompatClient if api_key is configured, else fast offline fallback client."""
    if config.llm and config.llm.api_key and config.llm.api_key.strip():
        return OpenAICompatClient.from_config(config)
    return _OfflineFallbackLLMClient()


def _sanitize_title(raw_title: str, fallback_prompt: str = "") -> str:
    """Cleans LLM title output into a concise 4-12 character/word summary without punctuation."""
    cleaned = str(raw_title or "").strip()
    cleaned = re.sub(r"^(标题|摘要|总结|Title|Summary)\s*[:：]\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip(" \t\r\n\"'“”‘’「」『』《》【】[]()（）.。!！?？,，;；")
    cleaned = cleaned.splitlines()[0].strip() if cleaned else ""

    if not cleaned:
        cleaned = _derive_fallback_title(fallback_prompt)

    if len(cleaned) > 16:
        cleaned = cleaned[:16].rstrip()
    return cleaned or "新对话摘要"


def _derive_fallback_title(prompt: str) -> str:
    """Derives a clean 4-8 character conversation title from the user's first prompt."""
    text = str(prompt or "").strip()
    text = re.sub(r"^(请帮我|帮我|请|我想|麻烦|在此基础上[:：]?)\s*", "", text)
    text = re.sub(r"[，。！？、,.!?；;：:\s]+", "", text)
    if not text:
        return "人像精修对话"
    return text[:8]


class GenerationWorker(QThread):
    """
    Background QThread bound to a specific session_id.
    Executes either the 3-layer ATBDraw retouching pipeline (Completer -> Planner -> Dispatcher)
    or plain-text LLM conversation without blocking the GUI thread.
    """

    progress_updated = Signal(str, str)       # session_id, status_message
    finished = Signal(str, object, str)       # session_id, WorkflowExecutionReport, saved_image_path
    text_finished = Signal(str, str)          # session_id, reply_text
    failed = Signal(str, str)                 # session_id, error_message
    token_received = Signal(str, str)         # session_id, delta_token
    tool_started = Signal(str, str, dict)     # session_id, tool_name, args
    tool_finished = Signal(str, str, dict)    # session_id, tool_name, metadata

    # New runtime bridge signals
    sig_subagent_state = Signal(str, str, str)  # subagent_id, state, detail
    sig_task_output = Signal(str, str)          # task_id, chunk
    sig_task_completed = Signal(str, int, str)  # task_id, exit_code, summary
    sig_ask_question = Signal(object, object)   # question_dict, response_future

    # Preserved aliases for unified desktop harness
    sig_token = Signal(str, str)                # session_id, delta_token
    sig_step_done = Signal(str, str)            # session_id, status_message
    sig_image_card = Signal(str, str)           # session_id, saved_image_path
    sig_error = Signal(str, str)                # session_id, error_message
    sig_finished = Signal(str, str)             # session_id, reply_text

    def __init__(
        self,
        session_id: str,
        prompt: str = "",
        attachment_path: Optional[str] = None,
        active_role_id: Optional[str] = None,
        active_plugin_id: Optional[str] = None,
        plugin_state: Optional[Dict[str, Any]] = None,
        config: Optional[AppConfig] = None,
        generated_images_dir: Optional[str] = None,
        llm_client: Optional[Any] = None,
        plugin: Optional[ATBMindPlugin] = None,
        delay_ms: int = 0,
        use_harness: bool = False,
        parent: Optional[QObject] = None,
        user_input: Optional[str] = None,
        event_bus: Optional[Any] = None,
        task_manager: Optional[Any] = None,
        orchestrator: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(parent)
        self.session_id = session_id
        effective_prompt = prompt or user_input or ""
        self.prompt = effective_prompt
        self.user_input = effective_prompt
        self.attachment_path = attachment_path or ""
        role_id = active_role_id or active_plugin_id
        self.active_role_id = role_id
        self.active_plugin_id = role_id
        self.plugin_state = dict(plugin_state or {})
        self.config = config or get_config()
        self.generated_images_dir = Path(
            generated_images_dir or "data/generated_images"
        )
        self.llm_client = llm_client or _build_default_llm_client(self.config)
        self.plugin = plugin
        self.delay_ms = delay_ms
        self.use_harness = use_harness
        self._is_cancelled = False
        self._cancel_event: Optional[Any] = None
        self._loop: Optional[Any] = None

        self.event_bus = None
        self.task_manager = None
        self.orchestrator = None
        self._attached_event_bus = None

        # Wire legacy signals to preserved aliases
        self.token_received.connect(self.sig_token)
        self.progress_updated.connect(self.sig_step_done)
        self.failed.connect(self.sig_error)
        self.text_finished.connect(self.sig_finished)

        if event_bus is None:
            from atbmind_core.runtime.event_bus import get_global_event_bus
            event_bus = get_global_event_bus()

        if task_manager is None:
            from atbmind_core.runtime.tasks import TaskManager
            task_manager = TaskManager(event_bus=event_bus)

        if orchestrator is None:
            from atbmind_core.runtime.subagents import SubagentOrchestrator
            orchestrator = SubagentOrchestrator(event_bus=event_bus)

        self.attach_runtime(event_bus, task_manager=task_manager, orchestrator=orchestrator)

    def attach_runtime(
        self,
        event_bus: Any,
        task_manager: Optional[Any] = None,
        orchestrator: Optional[Any] = None,
    ) -> None:
        """Connects AsyncEventBus and runtime components to Qt signal emitters."""
        if self._attached_event_bus is not None and self._attached_event_bus != event_bus:
            self.detach_runtime()

        self.event_bus = event_bus
        self.task_manager = task_manager
        self.orchestrator = orchestrator
        self._attached_event_bus = event_bus

        from atbmind_core.runtime.event_bus import (
            SubagentLifecycleEvent,
            TaskOutputEvent,
            TaskStatusChangedEvent,
            AskQuestionEvent,
        )

        event_bus.subscribe(SubagentLifecycleEvent, self.bridge_subagent_event)
        event_bus.subscribe(TaskOutputEvent, self.bridge_task_output_event)
        event_bus.subscribe(TaskStatusChangedEvent, self.bridge_task_status_event)
        event_bus.subscribe(AskQuestionEvent, self.bridge_ask_question_event)

    def detach_runtime(self) -> None:
        """Unsubscribes from currently attached AsyncEventBus."""
        if self._attached_event_bus is not None:
            try:
                from atbmind_core.runtime.event_bus import (
                    SubagentLifecycleEvent,
                    TaskOutputEvent,
                    TaskStatusChangedEvent,
                    AskQuestionEvent,
                )
                self._attached_event_bus.unsubscribe(SubagentLifecycleEvent, self.bridge_subagent_event)
                self._attached_event_bus.unsubscribe(TaskOutputEvent, self.bridge_task_output_event)
                self._attached_event_bus.unsubscribe(TaskStatusChangedEvent, self.bridge_task_status_event)
                self._attached_event_bus.unsubscribe(AskQuestionEvent, self.bridge_ask_question_event)
            except Exception as e:
                logger.debug("Failed unsubscribing from event bus: %s", e)
            self._attached_event_bus = None

    def bridge_subagent_event(self, event: Any) -> None:
        """Emits sig_subagent_state from SubagentLifecycleEvent."""
        subagent_id = getattr(event, "subagent_id", "") or getattr(event, "source_id", "")
        state = getattr(event, "state", "idle")
        detail = getattr(event, "detail", "")
        self.sig_subagent_state.emit(str(subagent_id), str(state), str(detail))

    def bridge_task_output_event(self, event: Any) -> None:
        """Emits sig_task_output from TaskOutputEvent."""
        task_id = getattr(event, "source_id", "") or getattr(event, "task_id", "")
        chunk = getattr(event, "chunk", "")
        self.sig_task_output.emit(str(task_id), str(chunk))

    def bridge_task_status_event(self, event: Any) -> None:
        """Emits sig_task_completed from TaskStatusChangedEvent."""
        task_id = getattr(event, "source_id", "") or getattr(event, "task_id", "")
        exit_code = getattr(event, "exit_code", None)
        if exit_code is None:
            new_status = getattr(event, "new_status", "")
            exit_code = 0 if new_status == "done" else (1 if new_status in ("failed", "killed") else 0)
        summary = getattr(event, "summary", "") or getattr(event, "new_status", "")
        self.sig_task_completed.emit(str(task_id), int(exit_code), str(summary))

    def bridge_ask_question_event(self, event: Any) -> None:
        """Emits sig_ask_question from AskQuestionEvent."""
        future = getattr(event, "response_future", getattr(event, "future", None))
        if isinstance(event, dict):
            q_dict = event
            future = event.get("future") or event.get("response_future")
        elif hasattr(event, "question_dict") and event.question_dict:
            q_dict = event.question_dict
        elif hasattr(event, "questions"):
            raw_questions = event.questions
            if hasattr(raw_questions, "model_dump"):
                q_list = raw_questions.model_dump()
            elif isinstance(raw_questions, list):
                q_list = [
                    q.model_dump() if hasattr(q, "model_dump") else q
                    for q in raw_questions
                ]
            else:
                q_list = raw_questions
            q_dict = {
                "questions": q_list,
                "tool_action": getattr(event, "tool_action", getattr(event, "toolAction", "")),
                "tool_summary": getattr(event, "tool_summary", getattr(event, "toolSummary", "")),
            }
        elif hasattr(event, "model_dump"):
            q_dict = event.model_dump()
        else:
            q_dict = {"questions": []}

        self.sig_ask_question.emit(q_dict, future)

    def stop(self) -> None:
        """Cascade cancel worker, cancel event, and task manager if attached."""
        self.cancel()
        if self.task_manager and hasattr(self.task_manager, "shutdown"):
            try:
                if self._loop and self._loop.is_running():
                    self._loop.call_soon_threadsafe(lambda: asyncio.create_task(self.task_manager.shutdown()))
                else:
                    asyncio.run(self.task_manager.shutdown())
            except Exception as exc:
                logger.debug("Failed shutting down task_manager on stop: %s", exc)

        if self.orchestrator and hasattr(self.orchestrator, "shutdown"):
            try:
                if self._loop and self._loop.is_running():
                    self._loop.call_soon_threadsafe(lambda: asyncio.create_task(self.orchestrator.shutdown()))
                else:
                    asyncio.run(self.orchestrator.shutdown())
            except Exception as exc:
                logger.debug("Failed shutting down orchestrator on stop: %s", exc)

    def cancel(self) -> None:
        """Marks this worker as cancelled so stale signals are suppressed and cancels harness stream."""
        self._is_cancelled = True
        if self._cancel_event and self._loop and self._loop.is_running():
            try:
                self._loop.call_soon_threadsafe(self._cancel_event.set)
            except Exception:
                pass
        self.detach_runtime()

    def run(self) -> None:
        if self.delay_ms > 0:
            self.msleep(self.delay_ms)

        if self._is_cancelled:
            return

        try:
            if self.use_harness:
                self._run_harness_pipeline()
            elif self.active_plugin_id == "draw":
                self._run_draw_pipeline()
            else:
                self._run_plain_text_pipeline()
        except Exception as exc:
            logger.warning("GenerationWorker failed for session %s: %s", self.session_id, exc)
            if not self._is_cancelled:
                self.failed.emit(self.session_id, str(exc))

    def _run_harness_pipeline(self) -> None:
        import asyncio
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._async_harness_run())
        finally:
            try:
                self._loop.close()
            except Exception:
                pass
            self._loop = None

    async def _async_harness_run(self) -> None:
        import asyncio
        from atbmind_core.harness import (
            AgentSession,
            AgentEventType,
            StreamClient,
            BashTool,
            ReadFileTool,
            WriteFileTool,
            EditFileTool,
            GrepTool,
            FindFilesTool,
            GenerateImageTool,
            RefineImageTool,
            SearchTemplatesTool,
        )

        from atbmind_core.skills.registry import SkillRegistry
        from atbmind_core.roles.registry import RoleRegistry
        from atbmind_core.roles.team import RobotTeam

        self._cancel_event = asyncio.Event()

        skill_reg = SkillRegistry()
        skill_reg.scan_directory(Path("skills"))
        role_reg = RoleRegistry(skill_registry=skill_reg)
        role_reg.scan_directory(Path("roles"))
        team = RobotTeam(leader_role_id="coordinator", role_registry=role_reg, skill_registry=skill_reg)

        if hasattr(self.llm_client, "stream_chat"):
            stream_client = self.llm_client
        else:
            base_url = self.config.llm.base_url if self.config.llm else "https://api.openai.com/v1"
            api_key = self.config.llm.api_key if self.config.llm else ""
            model = self.config.llm.model if self.config.llm else "gpt-4o"
            stream_client = StreamClient(base_url=base_url, api_key=api_key, model=model)

        accumulated_text = []
        last_image_path = None

        def event_listener(ev):
            nonlocal last_image_path
            if ev.type == AgentEventType.TOOL_CALL_START:
                t_name = ev.payload.get("name", "")
                t_args = ev.payload.get("arguments", {})
                self.tool_started.emit(self.session_id, t_name, t_args)
                self.progress_updated.emit(self.session_id, f"正在执行工具: {t_name}...")
            elif ev.type == AgentEventType.TOOL_CALL_END:
                t_name = ev.payload.get("name", "")
                meta = ev.payload.get("metadata", {})
                if isinstance(meta, dict) and "image_path" in meta:
                    last_image_path = meta["image_path"]
                self.tool_finished.emit(self.session_id, t_name, meta)

        session = team.create_coordinator_session(
            session_id=self.session_id,
            stream_client=stream_client,
            event_listener=event_listener,
        )


        async for event in session.prompt(self.prompt, cancellation_token=self._cancel_event):
            if self._is_cancelled or self._cancel_event.is_set():
                break

            if event.type == AgentEventType.MESSAGE_DELTA:
                delta = event.payload.get("delta", "")
                accumulated_text.append(delta)
                self.token_received.emit(self.session_id, delta)

            elif event.type == AgentEventType.TOOL_CALL_START:
                tool_name = event.payload.get("name", "")
                tool_args = event.payload.get("arguments", {})
                self.tool_started.emit(self.session_id, tool_name, tool_args)
                self.progress_updated.emit(self.session_id, f"正在执行工具: {tool_name}...")

            elif event.type == AgentEventType.TOOL_CALL_END:
                tool_name = event.payload.get("name", "")
                meta = event.payload.get("metadata", {})
                if "image_path" in meta:
                    last_image_path = meta["image_path"]
                self.tool_finished.emit(self.session_id, tool_name, meta)

            elif event.type == AgentEventType.AGENT_END:
                final_text = "".join(accumulated_text).strip()
                if last_image_path:
                    from atbmind_core.plugins.schemas import WorkflowExecutionReport
                    report = WorkflowExecutionReport(
                        request_id=str(uuid.uuid4()),
                        plugin_id="draw",
                        success=True,
                        final_output={"image_path": last_image_path},
                    )
                    self.finished.emit(self.session_id, report, last_image_path)
                self.text_finished.emit(self.session_id, final_text)

    def _run_plain_text_pipeline(self) -> None:
        self.progress_updated.emit(self.session_id, "正在生成回复...")
        messages = [
            {"role": "system", "content": "You are ATBMind, a helpful desktop AI assistant."},
            {"role": "user", "content": self.prompt},
        ]
        reply = self.llm_client.chat_completion(messages=messages)
        if not self._is_cancelled:
            self.text_finished.emit(self.session_id, str(reply).strip())

    def _run_draw_pipeline(self) -> None:
        plugin = self.plugin or DrawPlugin()
        completer = IntentCompleter(llm_client=self.llm_client)
        planner = WorkflowPlanner(llm_client=self.llm_client)
        dispatcher = SlotDispatcher()

        # Layer 1: Intent Completion
        self.progress_updated.emit(self.session_id, "Layer 1: 正在解析人像修图意图...")
        raw_input = {
            "image_path": self.attachment_path,
            "prompt": self.prompt,
            "plugin_state": self.plugin_state,
        }
        context_entities = plugin.extract_context_entities(raw_input)
        draft = completer.complete_intent(
            user_prompt=self.prompt,
            plugin=plugin,
            context_entities=context_entities,
        )

        # Resolve user-selected template from FooterDock plugin_state if specified
        available_templates = plugin.get_templates()
        matched_tpl = self._match_selected_template(
            str(self.plugin_state.get("template_id") or ""),
            available_templates,
        )
        if matched_tpl is not None:
            kws = list(draft.parameters.get("keywords") or [])
            kws.extend(matched_tpl.keywords)
            kws.append(matched_tpl.name)
            draft.parameters["keywords"] = kws
            draft.intent_category = matched_tpl.category

        if self._is_cancelled:
            return

        # Layer 2: Topological Workflow Planning
        self.progress_updated.emit(self.session_id, "Layer 2: 正在编排修图工作流...")
        plan = planner.plan_workflow(draft=draft, available_templates=available_templates)

        # Ensure at least one step exists (preferring matched_tpl if selected)
        if matched_tpl is not None and all(s.template_id != matched_tpl.template_id for s in plan.steps):
            default_slots = {
                k: (v.get("default") if isinstance(v, dict) else v)
                for k, v in matched_tpl.slot_definitions.items()
            }
            plan.steps.insert(
                0,
                WorkflowStep(
                    step=1,
                    template_id=matched_tpl.template_id,
                    name=matched_tpl.name,
                    slots=default_slots,
                ),
            )
            for idx, s in enumerate(plan.steps, start=1):
                s.step = idx
        elif not plan.steps and available_templates:
            first_tpl = available_templates[0]
            default_slots = {
                k: (v.get("default") if isinstance(v, dict) else v)
                for k, v in first_tpl.slot_definitions.items()
            }
            plan.steps.append(
                WorkflowStep(
                    step=1,
                    template_id=first_tpl.template_id,
                    name=first_tpl.name,
                    slots=default_slots,
                )
            )

        if self._is_cancelled:
            return

        # Layer 3: Slot Dispatch & Adapter Rendering
        self.progress_updated.emit(self.session_id, "Layer 3: 正在渲染精修图像...")
        initial_context = {
            "input_image": self.attachment_path or "canvas_source.png",
            "prompt": self.prompt,
            "plugin_state": dict(self.plugin_state),
        }
        report = dispatcher.dispatch_workflow(
            plan=plan,
            plugin=plugin,
            draft=draft,
            initial_context=initial_context,
            user_overrides=self.plugin_state,
        )

        if not report.success:
            err_msg = "人像修图管线执行失败"
            for sr in report.step_results:
                if not sr.success and sr.error_message:
                    err_msg = sr.error_message
                    break
            if not self._is_cancelled:
                self.failed.emit(self.session_id, err_msg)
            return

        # Persist generated image to data/generated_images/{uuid}.png
        self.generated_images_dir.mkdir(parents=True, exist_ok=True)
        image_filename = f"{uuid.uuid4().hex}.png"
        saved_image_path = self.generated_images_dir / image_filename

        raw_bytes = report.final_output.get("image_bytes")
        if isinstance(raw_bytes, (bytes, bytearray)) and len(raw_bytes) > 0:
            saved_image_path.write_bytes(bytes(raw_bytes))
        else:
            saved_image_path.write_bytes(_MINIMAL_PNG_BYTES)

        if not self._is_cancelled:
            self.finished.emit(self.session_id, report, str(saved_image_path))

    @staticmethod
    def _match_selected_template(selected_label: str, templates: list) -> Any:
        if not selected_label:
            return None
        label_clean = selected_label.strip()
        for t in templates:
            if t.template_id == label_clean or t.name == label_clean:
                return t
        # Substring fuzzy match (e.g. "双频原生磨皮" matches "双频原生肌理质感磨皮")
        for t in templates:
            if label_clean in t.name or t.name in label_clean:
                return t
            if any(kw in label_clean for kw in t.keywords):
                return t
        return None


class TitleWorker(QThread):
    """
    Background QThread bound to session_id.
    Queries LLM on the first turn of a session to generate a concise 4-8 word/character
    conversation title summary without blocking the UI.
    """

    title_generated = Signal(str, str)  # session_id, new_title

    def __init__(
        self,
        session_id: str,
        first_prompt: str,
        config: Optional[AppConfig] = None,
        llm_client: Optional[Any] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.session_id = session_id
        self.first_prompt = first_prompt
        self.config = config or get_config()
        self.llm_client = llm_client
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def run(self) -> None:
        if self._is_cancelled:
            return

        new_title = ""
        client = self.llm_client
        if client is None and self.config.llm and self.config.llm.api_key and self.config.llm.api_key.strip():
            client = OpenAICompatClient.from_config(self.config)

        if client is not None:
            try:
                messages = [
                    {
                        "role": "system",
                        "content": "请将用户的首条指令提炼为 4 到 8 个字的简短对话标题，不要包含引号或句号。",
                    },
                    {"role": "user", "content": self.first_prompt},
                ]
                raw = client.chat_completion(messages=messages)
                new_title = _sanitize_title(raw, fallback_prompt=self.first_prompt)
            except Exception as exc:
                logger.debug("TitleWorker LLM fallback for session %s: %s", self.session_id, exc)
                new_title = _derive_fallback_title(self.first_prompt)
        else:
            new_title = _derive_fallback_title(self.first_prompt)

        if not self._is_cancelled and new_title:
            self.title_generated.emit(self.session_id, new_title)
