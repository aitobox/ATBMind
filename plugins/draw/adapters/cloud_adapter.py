"""
ATBMind-Draw Cloud API Image Adapter
Connects to OpenAI/SiliconFlow/DALL-E compatible image generation & inpainting endpoints.
"""

from __future__ import annotations

import base64
import time
from typing import Any, Dict, Optional
import httpx

from plugins.draw.adapters.base import ImageAdapterResponse, ImageModelAdapter


class CloudAPIAdapter(ImageModelAdapter):
    """
    Cloud diffusion model API adapter supporting OpenAI / SiliconFlow image generation & editing endpoints.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self.config = config or {}
        self.base_url = str(self.config.get("base_url", "https://api.siliconflow.cn/v1")).rstrip("/")
        self.api_key = str(self.config.get("api_key", "sk-mock-cloud-key"))
        self.model = str(self.config.get("model", "black-forest-labs/FLUX.1-dev"))
        self.timeout = float(self.config.get("timeout", 30.0))
        self._client = http_client

    @property
    def adapter_type(self) -> str:
        return "cloud"

    def build_request_payload(
        self,
        template_id: str,
        slots: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        ctx = context or {}
        slot_desc = ", ".join(f"{k}={v}" for k, v in sorted(slots.items()))
        prompt = f"[Template {template_id}] Natural portrait retouching with parameters: {slot_desc}"
        return {
            "model": self.model,
            "prompt": prompt,
            "size": str(self.config.get("size", "1024x1024")),
            "response_format": str(self.config.get("response_format", "url")),
            "extra_body": {
                "template_id": template_id,
                "slots": dict(slots),
                "masks": ctx.get("masks", {}),
            },
        }

    def render_step(
        self,
        template_id: str,
        slots: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> ImageAdapterResponse:
        t0 = time.perf_counter()
        payload = self.build_request_payload(template_id, slots, context)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        endpoint = f"{self.base_url}/images/generations"

        close_after = False
        client = self._client
        if client is None:
            client = httpx.Client(timeout=self.timeout)
            close_after = True

        try:
            resp = client.post(endpoint, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            item = (data.get("data") or [{}])[0]
            img_url = item.get("url")
            img_bytes = None
            if item.get("b64_json"):
                img_bytes = base64.b64decode(item["b64_json"])

            latency_ms = (time.perf_counter() - t0) * 1000.0
            return ImageAdapterResponse(
                success=True,
                adapter_type=self.adapter_type,
                applied_template_id=template_id,
                applied_slots=dict(slots),
                image_bytes=img_bytes,
                image_url=img_url,
                latency_ms=latency_ms,
                metadata={"request_payload": payload, "endpoint": endpoint},
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - t0) * 1000.0
            return ImageAdapterResponse(
                success=False,
                adapter_type=self.adapter_type,
                applied_template_id=template_id,
                applied_slots=dict(slots),
                latency_ms=latency_ms,
                error_message=str(exc),
                metadata={"request_payload": payload, "endpoint": endpoint},
            )
        finally:
            if close_after:
                client.close()
