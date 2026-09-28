"""
ATBMind-Draw Offline Mock Image Adapter
Renders lightweight SVG/PNG image payloads with watermark overlays and deformation bounding boxes in < 5ms.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

from plugins.draw.adapters.base import ImageAdapterResponse, ImageModelAdapter


# Minimal valid 1x1 PNG header + trailer prefix so any PNG reader recognizes it,
# followed by embedded SVG/JSON overlay chunk for inspection.
_MINIMAL_PNG_HEADER = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
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
        embedded_payload = _MINIMAL_PNG_HEADER + b"\n<!--ATBMIND_OVERLAY:" + json.dumps(
            overlay_meta, ensure_ascii=False
        ).encode("utf-8") + b"-->"

        latency_ms = (time.perf_counter() - t0) * 1000.0
        return ImageAdapterResponse(
            success=True,
            adapter_type=self.adapter_type,
            applied_template_id=template_id,
            applied_slots=dict(slots),
            image_bytes=embedded_payload,
            image_url=f"mock://rendered/{template_id}.png",
            latency_ms=latency_ms,
            metadata=overlay_meta,
        )
