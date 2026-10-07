"""
ATBMind Domain Tools
Bridges ATBDraw adapters (Mock / Cloud) and portrait templates into AgentTools.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from atbmind_core.harness.tools.base import AgentTool, ExecutionMode, ToolResult
from atbmind_core.adapters.image import create_image_adapter

logger = logging.getLogger("atbmind.harness.tools.domain")

# Ensure image directory exists
IMAGE_DIR = os.path.join(os.getcwd(), "data", "generated_images")
os.makedirs(IMAGE_DIR, exist_ok=True)

# ----------------- 1. Generate Image Tool -----------------

class GenerateImageInput(BaseModel):
    prompt: str = Field(..., description="Image generation prompt describing subject, composition, and mood")
    style: Optional[str] = Field("portrait_photography", description="Art style, e.g. 'portrait_photography', 'cyberpunk', 'anime', 'chinese_style'")
    aspect_ratio: Optional[str] = Field("1:1", description="Aspect ratio, e.g. '1:1', '16:9', '9:16', '3:4'")
    template_id: Optional[str] = Field("T_DRAW_BODY_SLIM", description="Base retouching/generation template ID")

class GenerateImageTool(AgentTool):
    name = "generate_image"
    description = "Generate a new image using ATBDraw adapter with prompt, style, and aspect ratio."
    parameters_schema = GenerateImageInput
    execution_mode = ExecutionMode.SEQUENTIAL

    async def execute(self, args: Dict[str, Any], context: Optional[Any] = None) -> ToolResult:
        prompt = args.get("prompt", "").strip()
        style = args.get("style", "portrait_photography")
        aspect_ratio = args.get("aspect_ratio", "1:1")
        template_id = args.get("template_id", "T_DRAW_BODY_SLIM")

        if not prompt:
            return ToolResult(content="Error: prompt cannot be empty", is_error=True)

        try:
            adapter = create_image_adapter()
            resp = adapter.render_step(
                template_id=template_id,
                slots={
                    "prompt": prompt,
                    "style": style,
                    "aspect_ratio": aspect_ratio,
                },
            )

            if not resp.success:
                return ToolResult(
                    content=f"Image generation failed: {resp.error_message}",
                    is_error=True,
                )

            # Persist image to disk
            img_filename = f"gen_{uuid.uuid4().hex[:12]}.png"
            img_path = os.path.join(IMAGE_DIR, img_filename)

            if resp.image_bytes:
                with open(img_path, "wb") as f:
                    f.write(resp.image_bytes)
            else:
                with open(img_path, "wb") as f:
                    f.write(b"")

            metadata = {
                "image_path": img_path,
                "image_url": resp.image_url,
                "adapter_type": resp.adapter_type,
                "latency_ms": resp.latency_ms,
                "template_id": template_id,
                "applied_slots": resp.applied_slots,
            }

            return ToolResult(
                content=f"Image successfully generated and saved to: {img_path}",
                is_error=False,
                metadata=metadata,
            )
        except Exception as exc:
            logger.exception("Error in GenerateImageTool: %s", exc)
            return ToolResult(content=f"Error generating image: {exc}", is_error=True)

# ----------------- 2. Refine Image Tool -----------------

class RefineImageInput(BaseModel):
    source_image_path: str = Field(..., description="Local path to the source image to refine")
    instruction: str = Field(..., description="Refinement instructions (e.g. 'slim face slightly', 'enhance lighting')")
    intensity: Optional[float] = Field(0.5, description="Intensity of modification between 0.0 and 1.0")
    template_id: Optional[str] = Field("T_DRAW_BODY_SLIM", description="Retouching template ID")

class RefineImageTool(AgentTool):
    name = "refine_image"
    description = "Retouch or refine an existing image using ATBDraw adapter."
    parameters_schema = RefineImageInput
    execution_mode = ExecutionMode.SEQUENTIAL

    async def execute(self, args: Dict[str, Any], context: Optional[Any] = None) -> ToolResult:
        source_image_path = args.get("source_image_path", "")
        instruction = args.get("instruction", "")
        intensity = float(args.get("intensity", 0.5))
        template_id = args.get("template_id", "T_DRAW_BODY_SLIM")

        if not os.path.exists(source_image_path):
            return ToolResult(content=f"Error: source image not found at '{source_image_path}'", is_error=True)

        try:
            adapter = create_image_adapter()
            resp = adapter.render_step(
                template_id=template_id,
                slots={
                    "source_image": source_image_path,
                    "instruction": instruction,
                    "intensity": intensity,
                },
            )

            if not resp.success:
                return ToolResult(content=f"Image refinement failed: {resp.error_message}", is_error=True)

            img_filename = f"refine_{uuid.uuid4().hex[:12]}.png"
            img_path = os.path.join(IMAGE_DIR, img_filename)

            if resp.image_bytes:
                with open(img_path, "wb") as f:
                    f.write(resp.image_bytes)
            else:
                with open(img_path, "wb") as f:
                    f.write(b"")

            metadata = {
                "image_path": img_path,
                "source_image_path": source_image_path,
                "image_url": resp.image_url,
                "latency_ms": resp.latency_ms,
                "template_id": template_id,
            }

            return ToolResult(
                content=f"Image successfully refined and saved to: {img_path}",
                is_error=False,
                metadata=metadata,
            )
        except Exception as exc:
            logger.exception("Error in RefineImageTool: %s", exc)
            return ToolResult(content=f"Error refining image: {exc}", is_error=True)

# ----------------- 3. Search Templates Tool -----------------

class SearchTemplatesInput(BaseModel):
    keyword: Optional[str] = Field(None, description="Keyword to filter templates by name, keywords or category")
    category: Optional[str] = Field(None, description="Category filter (e.g. 'body_shaping', 'facial_micro_sculpting', 'skin_texture')")
    limit: int = Field(10, description="Maximum number of templates to return")

class SearchTemplatesTool(AgentTool):
    name = "search_templates"
    description = "Search ATBMind portrait retouching templates by keyword or category."
    parameters_schema = SearchTemplatesInput
    execution_mode = ExecutionMode.PARALLEL

    _cached_templates: Optional[List[Dict[str, Any]]] = None

    def _load_templates(self) -> List[Dict[str, Any]]:
        if self._cached_templates is not None:
            return self._cached_templates

        candidates = [
            os.path.join(os.getcwd(), "skills", "image_generation", "templates", "seed_templates.json"),
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "skills", "image_generation", "templates", "seed_templates.json"),
            os.path.join(os.getcwd(), "plugins", "draw", "templates", "seed_templates.json"),
        ]
        template_file = None
        for cand in candidates:
            if os.path.exists(cand):
                template_file = cand
                break
        if not template_file:
            return []

        try:
            with open(template_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    self._cached_templates = data
                elif isinstance(data, dict) and "templates" in data:
                    self._cached_templates = data["templates"]
                else:
                    self._cached_templates = []
        except Exception as exc:
            logger.warning("Failed to load seed templates: %s", exc)
            self._cached_templates = []

        return self._cached_templates

    async def execute(self, args: Dict[str, Any], context: Optional[Any] = None) -> ToolResult:
        keyword = (args.get("keyword") or "").strip().lower()
        category = (args.get("category") or "").strip().lower()
        limit = int(args.get("limit", 10))

        templates = self._load_templates()
        matched: List[Dict[str, Any]] = []

        for item in templates:
            t_id = str(item.get("template_id", item.get("id", "")))
            t_name = str(item.get("name", ""))
            t_cat = str(item.get("category", "")).lower()
            t_keywords = [str(k).lower() for k in item.get("keywords", [])]

            if category and category not in t_cat:
                continue

            if keyword:
                match_id = keyword in t_id.lower()
                match_name = keyword in t_name.lower()
                match_cat = keyword in t_cat
                match_kw = any(keyword in kw for kw in t_keywords)
                if not (match_id or match_name or match_cat or match_kw):
                    continue

            matched.append({
                "template_id": t_id,
                "name": t_name,
                "category": item.get("category", ""),
                "keywords": item.get("keywords", [])[:5],
            })
            if len(matched) >= limit:
                break

        if not matched:
            return ToolResult(
                content=f"No templates found matching keyword='{keyword}', category='{category}'",
                is_error=False,
                metadata={"count": 0},
            )

        lines = [f"Found {len(matched)} template(s):"]
        for m in matched:
            kw_str = ", ".join(m["keywords"])
            lines.append(f"- [{m['template_id']}] {m['name']} ({m['category']}) [标签: {kw_str}]")

        return ToolResult(
            content="\n".join(lines),
            is_error=False,
            metadata={"count": len(matched), "templates": matched},
        )
