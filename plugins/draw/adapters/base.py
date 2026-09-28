"""
ATBMind-Draw Image Model Adapter Base Interface
Defines the standard contract for offline mock rendering and cloud diffusion API adapters.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ImageAdapterResponse(BaseModel):
    """Standardized output returned by an ImageModelAdapter after rendering a workflow step."""

    success: bool = Field(..., description="Whether rendering succeeded")
    adapter_type: str = Field(..., description="Adapter identifier, e.g. 'mock' or 'cloud'")
    applied_template_id: str = Field(..., description="Executed template ID")
    applied_slots: Dict[str, Any] = Field(default_factory=dict, description="Applied slot parameters")
    image_bytes: Optional[bytes] = Field(default=None, description="Rendered image binary bytes")
    image_url: Optional[str] = Field(default=None, description="Rendered remote image URL if applicable")
    latency_ms: float = Field(0.0, description="Adapter execution time in milliseconds")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Watermark, bbox, or API metadata")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")


class ImageModelAdapter(ABC):
    """Abstract base class for image retouching/generation backends in ATBMind-Draw."""

    @property
    @abstractmethod
    def adapter_type(self) -> str:
        """Unique adapter identifier ('mock' or 'cloud')."""

    @abstractmethod
    def render_step(
        self,
        template_id: str,
        slots: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> ImageAdapterResponse:
        """Executes a single retouching/generation step and returns an ImageAdapterResponse."""


def create_image_adapter(config: Optional[Dict[str, Any]] = None) -> ImageModelAdapter:
    """Factory function to create the active image adapter based on configuration."""
    from plugins.draw.adapters.mock_adapter import MockImageAdapter
    from plugins.draw.adapters.cloud_adapter import CloudAPIAdapter

    cfg = config or {}
    adapter_name = str(cfg.get("adapter", "mock")).strip().lower()
    if adapter_name in ("cloud", "cloud_api", "siliconflow", "openai"):
        return CloudAPIAdapter(cfg)
    return MockImageAdapter(cfg)
