"""
ATBMind Offline Mock Image Adapter
Renders lightweight PNG image payloads with watermark overlays and deformation bounding boxes in < 5ms.
"""

from __future__ import annotations

import base64
import json
import time
from typing import Any, Dict, Optional

from atbmind_core.adapters.image.base import ImageAdapterResponse, ImageModelAdapter

# Standard valid 1x1 PNG byte array
_VALID_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


class MockImageAdapter(ImageModelAdapter):
    """
    GPU-free deterministic mock image adapter for instant (< 50ms) offline testing and UI preview.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}

    @property
    def adapter_type(self) -> str:
        return "mock"

    def render_step(
        self,
        template_id: str,
        slots: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> ImageAdapterResponse:
        t0 = time.perf_counter()
        ctx = context or {}
        watermark_text = f"ATBMind-Mock | {template_id} | slots={json.dumps(slots, ensure_ascii=False, sort_keys=True)}"
        deform_box = ctx.get("deform_bbox") or [0.20, 0.12, 0.80, 0.92]

        overlay_meta = {
            "watermark": watermark_text,
            "deform_bbox": deform_box,
            "template_id": template_id,
            "slots": dict(slots),
        }
        embedded_payload = _VALID_PNG_BYTES

        latency_ms = (time.perf_counter() - t0) * 1000.0
        return ImageAdapterResponse(
            success=True,
            adapter_type=self.adapter_type,
            applied_template_id=template_id,
            applied_slots=dict(slots),
            image_bytes=embedded_payload,
            latency_ms=latency_ms,
            metadata=overlay_meta,
        )
