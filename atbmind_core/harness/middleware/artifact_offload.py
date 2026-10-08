"""
ATBMind ArtifactOffloadMiddleware
Decouples heavy UI structures and large payloads from LLM context to prevent token bloat.
Inspired by TencentCloud/Octop OctopUiOffloadMiddleware design.
"""

from __future__ import annotations

import inspect
import json
import logging
from typing import Any, Dict, Optional
from atbmind_core.harness.tools.base import ToolResult

logger = logging.getLogger("atbmind.harness.middleware.artifact_offload")

class ArtifactOffloadMiddleware:
    """
    Middleware that intercepts ToolResults after tool execution.
    If the content is a JSON structure containing 'atbmind_ui' declaration and
    its character length exceeds the threshold (default 3000), the heavy payload
    is decoupled into `result.artifact`, while `result.content` is replaced by a
    compact summary referencing the artifact.
    """

    def __init__(self, threshold: int = 3000):
        self.threshold = threshold

    def process_tool_result(self, result: ToolResult) -> ToolResult:
        if result.is_error:
            return result

        if not result.content or len(result.content) < self.threshold:
            return result

        # Attempt to parse JSON content
        try:
            parsed = json.loads(result.content)
        except (json.JSONDecodeError, TypeError):
            return result

        if not isinstance(parsed, dict):
            return result

        # Check for atbmind_ui declaration
        has_ui = False
        ui_type = "generic_card"
        if parsed.get("atbmind_ui") is True:
            has_ui = True
            ui_type = parsed.get("ui_type") or parsed.get("type") or "generic_ui"
        elif isinstance(parsed.get("atbmind_ui"), dict):
            has_ui = True
            ui_type = parsed["atbmind_ui"].get("type") or "generic_ui"
        elif "ui_type" in parsed:
            has_ui = True
            ui_type = parsed["ui_type"]

        if not has_ui:
            return result

        # Extract title and summary text
        title = parsed.get("title") or parsed.get("name") or ui_type
        summary_text = parsed.get("summary") or parsed.get("description") or f"Rendered UI component: {title}"
        if len(summary_text) > 200:
            summary_text = summary_text[:197] + "..."

        lightweight_summary = {
            "data_ref": "artifact",
            "type": ui_type,
            "summary": summary_text,
        }

        # Decouple payload to artifact
        result.artifact = parsed
        result.content = json.dumps(lightweight_summary, ensure_ascii=False)
        result.metadata["offloaded"] = True

        logger.debug(
            "ArtifactOffloadMiddleware offloaded %d characters to artifact (type=%s)",
            len(result.content),
            ui_type,
        )
        return result

    async def __call__(self, context: Any, tool_call: Any, result: ToolResult) -> Optional[ToolResult]:
        return self.process_tool_result(result)
