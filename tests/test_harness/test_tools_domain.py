import asyncio
import os
import pytest
from atbmind_core.harness.tools.domain import (
    GenerateImageTool,
    RefineImageTool,
    SearchTemplatesTool,
)

def test_search_templates_tool():
    async def _run():
        tool = SearchTemplatesTool()
        res = await tool.execute({"keyword": "瘦身", "limit": 5})
        assert not res.is_error
        assert "T_" in res.content
        assert res.metadata["count"] > 0

    asyncio.run(_run())

def test_generate_image_tool_mock():
    async def _run():
        tool = GenerateImageTool()
        res = await tool.execute({
            "prompt": "Cyberpunk girl with neon lights",
            "style": "cyberpunk",
            "aspect_ratio": "16:9",
        })
        assert not res.is_error
        assert "image_path" in res.metadata
        img_path = res.metadata["image_path"]
        assert os.path.exists(img_path)
        assert img_path.endswith(".png")

    asyncio.run(_run())

def test_refine_image_tool_mock():
    async def _run():
        # First generate
        gen_tool = GenerateImageTool()
        gen_res = await gen_tool.execute({"prompt": "A test portrait"})
        source_path = gen_res.metadata["image_path"]

        # Refine
        refine_tool = RefineImageTool()
        ref_res = await refine_tool.execute({
            "source_image_path": source_path,
            "instruction": "Slim face slightly",
            "intensity": 0.3,
        })
        assert not ref_res.is_error
        assert "image_path" in ref_res.metadata
        assert os.path.exists(ref_res.metadata["image_path"])

    asyncio.run(_run())
