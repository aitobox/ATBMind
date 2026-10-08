from pathlib import Path
from PIL import Image
import pytest

BRAND_DIR = Path(__file__).resolve().parents[1] / "resource" / "assets" / "brand"


def test_brand_assets_files_exist_and_dimensions():
    required_pngs = {
        "mascot_hero.png": (1024, 1024),
        "mascot_avatar.png": (512, 512),
        "app_icon_1024.png": (1024, 1024),
        "app_icon_512.png": (512, 512),
        "app_icon_256.png": (256, 256),
        "app_icon_128.png": (128, 128),
        "app_icon_64.png": (64, 64),
        "app_icon_32.png": (32, 32),
        "app_icon_16.png": (16, 16),
    }
    for filename, (expected_w, expected_h) in required_pngs.items():
        file_path = BRAND_DIR / filename
        assert file_path.exists(), f"Asset {filename} does not exist at {file_path}"
        with Image.open(file_path) as img:
            assert img.size == (expected_w, expected_h), f"{filename} size {img.size} != {(expected_w, expected_h)}"
            assert img.mode in ("RGBA", "RGB")

    assert (BRAND_DIR / "app_icon.icns").exists(), "app_icon.icns does not exist"
