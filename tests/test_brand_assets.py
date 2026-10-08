from pathlib import Path
from PIL import Image
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon, QPixmap

BRAND_DIR = Path(__file__).resolve().parents[1] / "resource" / "assets" / "brand"


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(["--headless"])
    return app


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


def test_brand_assets_provider_methods(qapp):
    from apps.atbmind_desktop.theme import BrandAssets

    brand_dir = BrandAssets.get_brand_dir()
    assert brand_dir.exists()

    icon = BrandAssets.get_app_icon()
    assert isinstance(icon, QIcon)
    assert not icon.isNull()

    avatar = BrandAssets.get_mascot_avatar(26)
    assert isinstance(avatar, QPixmap)
    assert not avatar.isNull()
    assert avatar.width() == 26
    assert avatar.height() == 26

    hero = BrandAssets.get_mascot_hero()
    assert isinstance(hero, QPixmap)
    assert not hero.isNull()


def test_brand_assets_fallback_when_missing(qapp, monkeypatch, tmp_path):
    from apps.atbmind_desktop.theme import BrandAssets

    monkeypatch.setattr(BrandAssets, "get_brand_dir", lambda: tmp_path / "non_existent")
    # Reset caches
    BrandAssets._app_icon_cache = None
    BrandAssets._avatar_cache.clear()
    BrandAssets._hero_cache = None

    fallback_icon = BrandAssets.get_app_icon()
    assert isinstance(fallback_icon, QIcon)

    fallback_avatar = BrandAssets.get_mascot_avatar(26)
    assert isinstance(fallback_avatar, QPixmap)

    fallback_hero = BrandAssets.get_mascot_hero()
    assert isinstance(fallback_hero, QPixmap)


def test_main_window_has_brand_icon(qapp):
    from apps.atbmind_desktop.main import create_app
    from apps.atbmind_desktop.main_window import ATBMindMainWindow

    app = create_app(["--headless"])
    assert not app.windowIcon().isNull()
    win = ATBMindMainWindow()
    assert not win.windowIcon().isNull()

