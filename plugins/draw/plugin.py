"""
ATBMind-Draw Official Flagship Plugin Implementation
Implements ATBMindPlugin SPI for natural portrait retouching, body shaping, and intelligent workflow execution.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List

from atbmind_core.plugins.base import ATBMindPlugin
from atbmind_core.plugins.schemas import (
    PluginUISpec,
    TemplateMetadata,
    WorkflowResult,
    WorkflowStep,
)
from plugins.draw.adapters.base import ImageModelAdapter, create_image_adapter
from plugins.draw.prompts.injection import get_draw_domain_prompt_injection
from plugins.draw.vision.extractor import DrawVisionExtractor

logger = logging.getLogger(__name__)

SEED_TEMPLATES_PATH = Path(__file__).resolve().parent / "templates" / "seed_templates.json"

DRAW_UI_MODELS: List[str] = [
    "Seedream 4.5",
    "Flux.1",
    "SDXL",
    "Mock Adapter",
]

DRAW_UI_ASPECT_RATIOS: List[str] = [
    "自动",
    "1:1",
    "16:9",
    "9:16",
    "3:4",
]

DRAW_UI_STYLES: List[Dict[str, str]] = [
    {"id": "portrait", "name": "人像摄影", "icon": "📷", "prompt_suffix": "masterpiece portrait photography, 85mm lens, natural skin texture, soft studio lighting"},
    {"id": "cinematic", "name": "电影写真", "icon": "🎬", "prompt_suffix": "cinematic film still, anamorphic lens, moody lighting, rich color grading"},
    {"id": "guofeng", "name": "中国风", "icon": "🏮", "prompt_suffix": "traditional Chinese aesthetic, oriental elegance, delicate silk texture, atmospheric lighting"},
    {"id": "anime", "name": "动漫", "icon": "✨", "prompt_suffix": "high quality anime illustration, clean cel shading, vibrant expressive colors"},
    {"id": "render_3d", "name": "3D渲染", "icon": "🧊", "prompt_suffix": "Octane 3D render, subsurface scattering, Pixar/Disney stylized lighting, ultra detailed"},
    {"id": "cyberpunk", "name": "赛博朋克", "icon": "🌃", "prompt_suffix": "cyberpunk neon lighting, futuristic metropolis, holographic reflections, high contrast"},
    {"id": "ink_wash", "name": "水墨画", "icon": "🖌️", "prompt_suffix": "traditional Chinese ink wash painting, sumi-e brushwork, poetic negative space"},
    {"id": "oil_painting", "name": "油画", "icon": "🎨", "prompt_suffix": "classical oil painting on canvas, rich impasto brushstrokes, Rembrandt lighting"},
    {"id": "classical", "name": "古典", "icon": "🏛️", "prompt_suffix": "vintage classical portrait, timeless fine art composition, warm museum lighting"},
    {"id": "watercolor", "name": "水彩画", "icon": "💧", "prompt_suffix": "delicate watercolor illustration, soft pigment bleed, textured cold-press paper"},
]

DEFAULT_DRAW_TEMPLATES: List[TemplateMetadata] = [
    TemplateMetadata(
        template_id="T_DRAW_BODY_SLIM",
        name="智能全身自然显瘦塑形",
        category="body_shaping",
        keywords=["瘦身", "显瘦", "瘦腰", "微胖", "塑形", "slim", "body"],
        target_scope="single_person",
        slot_definitions={
            "intensity": {"type": "float", "default": 0.15},
            "preserve_background": {"type": "bool", "default": True},
        },
        dependencies=[],
    ),
    TemplateMetadata(
        template_id="T_DRAW_CLOTH_PROTECT",
        name="服装纹理与边缘防畸变锁定",
        category="cloth_background",
        keywords=["衣服保护", "防变形", "边缘锁定", "clothing", "protect"],
        target_scope="single_person",
        slot_definitions={
            "preserve_ratio": {"type": "float", "default": 0.85},
            "edge_feather_px": {"type": "int", "default": 10},
        },
        dependencies=["T_DRAW_BODY_SLIM"],
    ),
    TemplateMetadata(
        template_id="T_DRAW_SKIN_TEXTURE",
        name="双频原生肌理质感磨皮",
        category="skin_lighting",
        keywords=["磨皮", "祛痘", "肤质", "通透", "清透", "skin", "retouch"],
        target_scope="single_person",
        slot_definitions={
            "smooth_strength": {"type": "float", "default": 0.45},
            "preserve_skin_texture": {"type": "bool", "default": True},
            "protect_catchlights": {"type": "bool", "default": True},
        },
        dependencies=[],
    ),
    TemplateMetadata(
        template_id="T_DRAW_FACE_CONTOUR",
        name="面部立体轮廓与下颌线微雕",
        category="face_sculpting",
        keywords=["瘦脸", "下颌线", "脸型", "小脸", "轮廓", "face", "jawline"],
        target_scope="single_person",
        slot_definitions={
            "intensity": {"type": "float", "default": 0.14},
            "neck_transition_smooth": {"type": "bool", "default": True},
        },
        dependencies=[],
    ),
]


def load_draw_seed_templates(seed_path: Path = SEED_TEMPLATES_PATH) -> List[TemplateMetadata]:
    """Loads curated portrait retouching templates from seed_templates.json."""
    if seed_path.is_file():
        try:
            raw = json.loads(seed_path.read_text(encoding="utf-8"))
            if isinstance(raw, list) and raw:
                return [TemplateMetadata.model_validate(item) for item in raw]
        except Exception as exc:
            logger.warning("Failed to load seed_templates.json (%s), using defaults", exc)
    return list(DEFAULT_DRAW_TEMPLATES)


class DrawPlugin(ATBMindPlugin):
    """
    ATBMind-Draw Flagship Plugin (plugin_id='draw').
    Provides portrait entity/mask extraction, domain prompt injection, and template step execution.
    """

    def __init__(self) -> None:
        self._config: Dict[str, Any] = {}
        self._extractor = DrawVisionExtractor()
        self._templates: List[TemplateMetadata] = load_draw_seed_templates()
        self.adapter: ImageModelAdapter = create_image_adapter()

    @property
    def plugin_id(self) -> str:
        return "draw"

    @property
    def version(self) -> str:
        return "1.0.0"

    def initialize(self, config: Dict[str, Any]) -> None:
        self._config = dict(config or {})
        self._extractor = DrawVisionExtractor(self._config)
        self.adapter = create_image_adapter(self._config)
        custom_seed = self._config.get("seed_templates_path")
        if custom_seed:
            self._templates = load_draw_seed_templates(Path(str(custom_seed)))
        else:
            self._templates = load_draw_seed_templates()

    def get_templates(self) -> List[TemplateMetadata]:
        return list(self._templates)

    def get_ui_spec(self) -> PluginUISpec:
        """
        Returns the Doubao-style UI specification for ATBDraw, including
        models, aspect ratios, art styles, and portrait retouching templates.
        """
        return PluginUISpec(
            plugin_id=self.plugin_id,
            display_name="图像生成 (ATBDraw)",
            icon="🖼️",
            supports_attachments=True,
            attachment_types=[".png", ".jpg", ".jpeg", ".webp"],
            models=list(DRAW_UI_MODELS),
            aspect_ratios=list(DRAW_UI_ASPECT_RATIOS),
            styles=[dict(s) for s in DRAW_UI_STYLES],
            templates=self.get_templates(),
        )

    def extract_context_entities(self, raw_input: Any) -> Dict[str, Any]:
        return self._extractor.extract(raw_input)

    def get_domain_prompt_injection(self) -> str:
        return get_draw_domain_prompt_injection()

    def execute_workflow_step(self, step: WorkflowStep, context: Dict[str, Any]) -> WorkflowResult:
        start_t = time.perf_counter()
        input_asset = (
            context.get("previous_output", {}).get("rendered_asset")
            if isinstance(context.get("previous_output"), dict)
            else None
        ) or context.get("input_image", "canvas_source.png")

        adapter_res = self.adapter.render_step(
            template_id=step.template_id,
            slots=step.slots,
            context=context,
        )
        rendered_asset = f"{input_asset}->{step.template_id}"
        elapsed_ms = (time.perf_counter() - start_t) * 1000.0

        return WorkflowResult(
            step=step.step,
            success=adapter_res.success,
            output_data={
                "plugin_id": self.plugin_id,
                "template_id": step.template_id,
                "step_name": step.name,
                "applied_slots": dict(step.slots),
                "rendered_asset": rendered_asset,
                "adapter_type": adapter_res.adapter_type,
                "image_bytes": adapter_res.image_bytes,
                "image_url": adapter_res.image_url,
                "adapter_metadata": adapter_res.metadata,
            },
            execution_time_ms=elapsed_ms,
            error_message=adapter_res.error_message,
        )
