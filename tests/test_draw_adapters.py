import base64
import httpx

from atbmind_core.adapters.image.base import create_image_adapter
from atbmind_core.adapters.image.cloud_adapter import CloudAPIAdapter
from atbmind_core.adapters.image.mock_adapter import MockImageAdapter


def test_mock_image_adapter_latency_and_watermark():
    """Verify MockImageAdapter finishes in < 50ms and embeds watermark + deform_bbox."""
    adapter = MockImageAdapter()
    res = adapter.render_step(
        template_id="T_DRAW_BODY_SLIM",
        slots={"intensity": 0.16, "preserve_background": True},
        context={"deform_bbox": [0.22, 0.15, 0.78, 0.90]},
    )

    assert res.success is True
    assert res.adapter_type == "mock"
    assert res.latency_ms < 50.0
    assert res.image_bytes is not None
    assert res.image_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    assert "T_DRAW_BODY_SLIM" in res.metadata["watermark"]
    assert res.metadata["deform_bbox"] == [0.22, 0.15, 0.78, 0.90]


def test_cloud_api_adapter_request_and_b64_parsing():
    """Verify CloudAPIAdapter constructs request payload and parses b64_json/url via mock httpx transport."""
    fake_png = b"\x89PNG\r\n\x1a\nCLOUD_IMAGE"
    b64_payload = base64.b64encode(fake_png).decode("ascii")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/images/generations")
        assert request.headers["Authorization"] == "Bearer sk-test-cloud"
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "url": "https://cdn.example.com/retouched_01.png",
                        "b64_json": b64_payload,
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    adapter = CloudAPIAdapter(
        config={"api_key": "sk-test-cloud", "model": "FLUX.1-dev"},
        http_client=client,
    )

    res = adapter.render_step(
        template_id="T_DRAW_SKIN_TEXTURE",
        slots={"smooth_strength": 0.40},
        context={"masks": {"face_mask": {"region_id": "m1"}}},
    )

    assert res.success is True
    assert res.adapter_type == "cloud"
    assert res.image_url == "https://cdn.example.com/retouched_01.png"
    assert res.image_bytes == fake_png
    client.close()


def test_dynamic_adapter_factory():
    """Verify create_image_adapter dynamically instantiates MockImageAdapter and CloudAPIAdapter via config."""
    mock_ad = create_image_adapter({"adapter": "mock"})
    assert isinstance(mock_ad, MockImageAdapter)

    res = mock_ad.render_step(template_id="T_DRAW_BODY_SLIM", slots={"intensity": 0.15})
    assert res.success is True
    assert res.adapter_type == "mock"
    assert res.image_bytes.startswith(b"\x89PNG")

    cloud_ad = create_image_adapter({"adapter": "cloud", "api_key": "sk-live"})
    assert isinstance(cloud_ad, CloudAPIAdapter)
    assert isinstance(create_image_adapter({"adapter": "siliconflow"}), CloudAPIAdapter)

