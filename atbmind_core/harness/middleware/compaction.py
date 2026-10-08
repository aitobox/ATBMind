"""ATBMind ContextCompactionMiddleware.

Adaptive sliding-window compaction and summarization to prevent LLM context overflow.
Inspired by TencentCloud/Octop compaction.py and ContextUsageMiddleware designs.
"""

from __future__ import annotations

import inspect
import logging
from typing import Any, Awaitable, Callable, List, Optional

from atbmind_core.harness.types import AgentMessage, Role

logger = logging.getLogger("atbmind.harness.middleware.compaction")


class ContextCompactionMiddleware:
    """Middleware that monitors conversational token budgets and compacts historical turns.

    Preserves:
      - The initial System Prompt (if present).
      - The most recent K interaction turns (default 3).
    Folds the intermediate messages into a single summary message:
      [Conversation Summary: Earlier discussion folded for brevity]
    """

    def __init__(
        self,
        max_tokens_budget: int = 4000,
        keep_recent_turns: int = 3,
        summarize_fn: Optional[Callable[[List[AgentMessage]], Awaitable[str]]] = None,
    ) -> None:
        self.max_tokens_budget = max_tokens_budget
        self.keep_recent_turns = keep_recent_turns
        self.summarize_fn = summarize_fn

    def estimate_tokens(
        self, messages: List[AgentMessage], system_prompt: Optional[str] = None
    ) -> int:
        """Estimate token consumption using character heuristic (~4 chars/token)."""
        total_chars = len(system_prompt) if system_prompt else 0
        for m in messages:
            if m.content:
                total_chars += len(m.content)
            if m.tool_calls:
                for tc in m.tool_calls:
                    total_chars += len(tc.name) + len(str(tc.arguments))
        return max(1, total_chars // 4)

    def should_compact(
        self, messages: List[AgentMessage], system_prompt: Optional[str] = None
    ) -> bool:
        """Determine whether context length exceeds budget and has sufficient history to fold."""
        min_required = self.keep_recent_turns + 2
        if len(messages) < min_required:
            return False

        estimated = self.estimate_tokens(messages, system_prompt)
        return estimated > self.max_tokens_budget

    async def compact(
        self,
        messages: List[AgentMessage],
        summarize_fn: Optional[Callable[[List[AgentMessage]], Awaitable[str]]] = None,
    ) -> List[AgentMessage]:
        """Compact messages by folding middle history into a concise summary."""
        if len(messages) <= self.keep_recent_turns + 1:
            return list(messages)

        start_idx = 0
        first_system: Optional[AgentMessage] = None
        if messages and messages[0].role == Role.SYSTEM:
            first_system = messages[0]
            start_idx = 1

        keep_k = max(1, self.keep_recent_turns)
        end_idx = len(messages) - keep_k

        if start_idx >= end_idx:
            return list(messages)

        middle_messages = messages[start_idx:end_idx]
        recent_messages = messages[end_idx:]

        fn = summarize_fn or self.summarize_fn
        if fn:
            res = fn(middle_messages)
            if inspect.isawaitable(res):
                summary_text = await res
            else:
                summary_text = str(res)
        else:
            summary_text = self._extractive_summary(middle_messages)

        summary_msg = AgentMessage(
            role=Role.USER,
            content=f"[Conversation Summary: Earlier discussion folded for brevity]\n{summary_text}",
        )

        result: List[AgentMessage] = []
        if first_system:
            result.append(first_system)
        result.append(summary_msg)
        result.extend(recent_messages)

        logger.info(
            "Context compacted: reduced %d messages to %d messages (folded %d turns)",
            len(messages),
            len(result),
            len(middle_messages),
        )
        return result

    def _extractive_summary(self, messages: List[AgentMessage]) -> str:
        """Generate structured extractive summary from dialogue messages."""
        lines: List[str] = []
        for m in messages:
            role_str = getattr(m.role, "value", str(m.role))
            snippet = (m.content or "").strip()
            if len(snippet) > 120:
                snippet = snippet[:117] + "..."
            if snippet:
                lines.append(f"- {role_str.upper()}: {snippet}")
            elif m.tool_calls:
                call_names = ", ".join(tc.name for tc in m.tool_calls)
                lines.append(f"- {role_str.upper()} [tools]: {call_names}")
        return "\n".join(lines)

    async def process_context(self, context: Any) -> None:
        """Hook method called before each turn in agent_loop."""
        messages = getattr(context, "messages", None)
        if messages is None:
            return

        system_prompt = getattr(context, "system_prompt", None)
        if self.should_compact(messages, system_prompt):
            compacted = await self.compact(messages)
            context.messages = compacted
