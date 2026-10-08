#!/usr/bin/env python3
"""
Generate and process brand assets for ATBMind Desktop.
Produces multi-resolution PNG icons, transparent avatars, and macOS ICNS bundles.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageFilter, ImageOps

ROOT_DIR = Path(__file__).resolve().parents[1]
BRAND_DIR = ROOT_DIR / "resource" / "assets" / "brand"

HERO_SOURCE = Path(
    "/Users/brainzhang/.gemini/antigravity/brain/7a2d0bf2-9f16-49a7-b99b-1d3e61ea41b1/mascot_hero_1791421119252.jpg"
)
ICON_SOURCE = Path(
    "/Users/brainzhang/.gemini/antigravity/brain/7a2d0bf2-9f16-49a7-b99b-1d3e61ea41b1/mascot_icon_1791421135420.jpg"
)

SIZES = [1024, 512, 256, 128, 64, 32, 16]


def create_transparent_avatar(icon_img: Image.Image, output_path: Path, size: int = 512) -> None:
    """Creates a circular/squircle transparent avatar focused on the mascot face."""
    w, h = icon_img.size
    # Crop central region (60% width, 60% height around center-upper area)
    crop_box = (int(w * 0.18), int(h * 0.18), int(w * 0.82), int(h * 0.82))
    cropped = icon_img.crop(crop_box).resize((size, size), Image.Resampling.LANCZOS)
    
    # Create circular mask with antialiasing
    mask = Image.new("L", (size * 4, size * 4), 0)
    from PIL import ImageDraw
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size * 4 - 1, size * 4 - 1), fill=255)
    mask = mask.resize((size, size), Image.Resampling.LANCZOS)
    
    avatar = cropped.convert("RGBA")
    avatar.putalpha(mask)
    avatar.save(output_path, "PNG")


def generate_png_sizes(master_icon: Image.Image, brand_dir: Path) -> None:
    """Downsamples master icon into standard resolutions."""
    for s in SIZES:
        out_file = brand_dir / f"app_icon_{s}.png"
        resized = master_icon.resize((s, s), Image.Resampling.LANCZOS)
        if s <= 32:
            # Subtle sharpening for tiny icons
            resized = resized.filter(ImageFilter.UnsharpMask(radius=1.0, percent=120, threshold=3))
        resized.save(out_file, "PNG", optimize=True)


def generate_icns(brand_dir: Path) -> None:
    """Builds macOS native .icns bundle from icon set."""
    iconset_dir = brand_dir / "app_icon.iconset"
    iconset_dir.mkdir(parents=True, exist_ok=True)

    master = Image.open(brand_dir / "app_icon_1024.png").convert("RGBA")

    # Apple iconutil expected naming:
    # icon_16x16.png, icon_16x16@2x.png (32), icon_32x32.png, icon_32x32@2x.png (64), ...
    specs = [
        ("icon_16x16.png", 16),
        ("icon_16x16@2x.png", 32),
        ("icon_32x32.png", 32),
        ("icon_32x32@2x.png", 64),
        ("icon_128x128.png", 128),
        ("icon_128x128@2x.png", 256),
        ("icon_256x256.png", 256),
        ("icon_256x256@2x.png", 512),
        ("icon_512x512.png", 512),
        ("icon_512x512@2x.png", 1024),
    ]

    for name, sz in specs:
        target = iconset_dir / name
        im = master.resize((sz, sz), Image.Resampling.LANCZOS)
        im.save(target, "PNG")

    icns_path = brand_dir / "app_icon.icns"
    if sys.platform == "darwin" and shutil.which("iconutil"):
        try:
            subprocess.run(
                ["iconutil", "-c", "icns", str(iconset_dir), "-o", str(icns_path)],
                check=True,
                capture_output=True,
            )
        except Exception as e:
            print(f"Warning: iconutil failed ({e}), falling back to PIL ICNS export")
            master.save(icns_path, format="ICNS")
    else:
        master.save(icns_path, format="ICNS")

    shutil.rmtree(iconset_dir, ignore_errors=True)


def build_all_assets() -> None:
    BRAND_DIR.mkdir(parents=True, exist_ok=True)

    print("Processing mascot hero image...")
    hero = Image.open(HERO_SOURCE).convert("RGBA").resize((1024, 1024), Image.Resampling.LANCZOS)
    hero.save(BRAND_DIR / "mascot_hero.png", "PNG", optimize=True)

    print("Processing master app icon...")
    icon = Image.open(ICON_SOURCE).convert("RGBA").resize((1024, 1024), Image.Resampling.LANCZOS)
    icon.save(BRAND_DIR / "app_icon_1024.png", "PNG", optimize=True)

    print("Generating avatar cutout...")
    create_transparent_avatar(icon, BRAND_DIR / "mascot_avatar.png", size=512)

    print("Downsampling multi-resolution icons...")
    generate_png_sizes(icon, BRAND_DIR)

    print("Building macOS ICNS bundle...")
    generate_icns(BRAND_DIR)

    print("All brand assets generated successfully in:", BRAND_DIR)


def main():
    parser = argparse.ArgumentParser(description="ATBMind Brand Assets Generator")
    parser.add_argument("--verify", action="store_true", help="Verify all assets exist and are valid")
    args = parser.parse_args()

    if args.verify:
        required = [
            "mascot_hero.png",
            "mascot_avatar.png",
            "app_icon_1024.png",
            "app_icon_512.png",
            "app_icon_256.png",
            "app_icon_128.png",
            "app_icon_64.png",
            "app_icon_32.png",
            "app_icon_16.png",
            "app_icon.icns",
        ]
        all_ok = True
        for f in required:
            p = BRAND_DIR / f
            if not p.exists() or p.stat().st_size == 0:
                print(f"[FAIL] Missing or empty: {f}")
                all_ok = False
            else:
                print(f"[OK] {f} ({p.stat().st_size} bytes)")
        if not all_ok:
            sys.exit(1)
        print("All brand assets verified OK!")
        return

    build_all_assets()


if __name__ == "__main__":
    main()
