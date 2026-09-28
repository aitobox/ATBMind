#!/usr/bin/env python3
"""
ATBMind-Draw Seed Templates Generator & Validator
Validates template metadata JSON structure, uniqueness, DAG dependencies, and SQLite bulk import.
Can also generate `plugins/draw/templates/seed_templates.json` with 360 curated portrait retouching templates.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from atbmind_core.plugins.schemas import TemplateMetadata
from atbmind_core.storage.db import TemplateStore


def _extract_csv_portrait_snippets(csv_path: Path, max_count: int = 80) -> List[Dict[str, str]]:
    snippets: List[Dict[str, str]] = []
    if not csv_path.is_file():
        return snippets
    try:
        with csv_path.open("r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                title = (row.get("title") or "").strip()
                desc = (row.get("description") or "").strip()
                text_lower = f"{title} {desc}".lower()
                if any(k in text_lower for k in ("portrait", "fashion", "lighting", "skin", "editorial", "face", "body", "studio")):
                    snippets.append({"id": str(row.get("id") or ""), "title": title, "description": desc})
                    if len(snippets) >= max_count:
                        break
    except Exception:
        pass
    return snippets


def generate_seed_templates(csv_path: Path | None = None) -> List[Dict[str, Any]]:
    csv_snippets = _extract_csv_portrait_snippets(csv_path or (ROOT_DIR / "resource" / "ATBDraw-prompts.csv"))
    templates: List[Dict[str, Any]] = []

    # 1. Core canonical anchors (preserved for backward compatibility with existing tests & benchmarks)
    canonical = [
        {
            "template_id": "T_DRAW_BODY_SLIM",
            "name": "智能全身自然显瘦塑形",
            "category": "body_shaping",
            "keywords": ["瘦身", "显瘦", "瘦腰", "微胖", "塑形", "slim", "body", "全身显瘦"],
            "target_scope": "single_person",
            "slot_definitions": {
                "intensity": {"type": "float", "default": 0.15},
                "preserve_background": {"type": "bool", "default": True},
            },
            "dependencies": [],
        },
        {
            "template_id": "T_DRAW_CLOTH_PROTECT",
            "name": "服装纹理与边缘防畸变锁定",
            "category": "cloth_background",
            "keywords": ["衣服保护", "防变形", "边缘锁定", "clothing", "protect", "background_lock"],
            "target_scope": "single_person",
            "slot_definitions": {
                "preserve_ratio": {"type": "float", "default": 0.85},
                "edge_feather_px": {"type": "int", "default": 10},
            },
            "dependencies": ["T_DRAW_BODY_SLIM"],
        },
        {
            "template_id": "T_DRAW_SKIN_TEXTURE",
            "name": "双频原生肌理质感磨皮",
            "category": "skin_lighting",
            "keywords": ["磨皮", "祛痘", "肤质", "通透", "清透", "skin", "retouch"],
            "target_scope": "single_person",
            "slot_definitions": {
                "smooth_strength": {"type": "float", "default": 0.45},
                "preserve_skin_texture": {"type": "bool", "default": True},
                "protect_catchlights": {"type": "bool", "default": True},
            },
            "dependencies": [],
        },
        {
            "template_id": "T_DRAW_FACE_CONTOUR",
            "name": "面部立体轮廓与下颌线微雕",
            "category": "face_sculpting",
            "keywords": ["瘦脸", "下颌线", "脸型", "小脸", "轮廓", "face", "jawline"],
            "target_scope": "single_person",
            "slot_definitions": {
                "intensity": {"type": "float", "default": 0.14},
                "neck_transition_smooth": {"type": "bool", "default": True},
            },
            "dependencies": [],
        },
    ]
    templates.extend(canonical)

    # 2. Cloth & Background Anti-Distortion Lock Templates (89 items -> total 90 in cloth_background)
    cloth_actions = [
        ("CLOTH_EDGE", "高刚性服装轮廓防拉扯锁定", ["衣服边缘", "防拉扯", "版型锁定", "clothing_edge"]),
        ("BG_GRID", "背景建筑竖线与地平线透视保护", ["背景防歪", "门框保护", "透视锁定", "background_grid"]),
        ("STRIPE_GUARD", "条纹格纹衣物几何纹理保真", ["条纹保护", "格纹防变形", "图案锁定", "plaid_guard"]),
        ("HAIR_BOUNDARY", "发丝边缘与肩颈交界羽化隔离", ["发丝保护", "肩颈边界", "抠图羽化", "hair_feather"]),
        ("COLLAR_LOCK", "领口与项链饰品几何刚性约束", ["领口防变形", "项链保护", "刚性约束", "collar_rigid"]),
    ]
    for idx in range(1, 90):
        code, base_name, kws = cloth_actions[(idx - 1) % len(cloth_actions)]
        scene_tag = ["全身街拍", "室内棚拍", "逆光外景", "近景半身", "职场正装"][(idx - 1) % 5]
        tid = f"T_CLOTH_BG_{idx:03d}"
        templates.append(
            {
                "template_id": tid,
                "name": f"{scene_tag}·{base_name} #{idx:02d}",
                "category": "cloth_background",
                "keywords": kws + [scene_tag, code.lower()],
                "target_scope": "single_person" if idx % 3 != 0 else "background",
                "slot_definitions": {
                    "preserve_ratio": {"type": "float", "default": round(0.80 + (idx % 15) * 0.01, 2)},
                    "grid_stiffness": {"type": "float", "default": 0.90},
                    "feather_radius": {"type": "int", "default": 6 + (idx % 10)},
                },
                "dependencies": [],
            }
        )

    # 3. Body Shaping Templates (89 items -> total 90 in body_shaping)
    body_actions = [
        ("WAIST_SLIM", "自然S型折角收腰与腹部平坦精修", ["瘦腰", "收腹", "小蛮腰", "腰线", "waist", "tummy"]),
        ("SHOULDER_NECK", "直角肩与天鹅颈斜方肌弱化塑形", ["直角肩", "天鹅颈", "斜方肌", "肩颈", "shoulder", "neck"]),
        ("LEG_ELONGATE", "黄金比例小腿修长与腿型笔直矫正", ["长腿", "大长腿", "瘦腿", "小腿", "XO型腿", "legs"]),
        ("ARM_BACK_THIN", "上臂拜拜肉纤细与少女背薄化调整", ["瘦手臂", "拜拜肉", "薄背", "少女背", "arm", "back"]),
        ("HIP_POSTURE", "假胯宽内收与骨盆体态挺拔矫正", ["假胯宽", "提臀", "体态", "挺拔", "显瘦", "posture", "hip"]),
    ]
    for idx in range(1, 90):
        code, base_name, kws = body_actions[(idx - 1) % len(body_actions)]
        intensity_tier = ["微调自然档", "标准匀称档", "上镜精修档"][(idx - 1) % 3]
        tid = f"T_BODY_SHAPE_{idx:03d}"
        guard_dep = f"T_CLOTH_BG_{idx:03d}"
        templates.append(
            {
                "template_id": tid,
                "name": f"{intensity_tier}·{base_name} #{idx:02d}",
                "category": "body_shaping",
                "keywords": kws + [intensity_tier, code.lower(), "人像修形"],
                "target_scope": "single_person",
                "slot_definitions": {
                    "intensity": {"type": "float", "default": round(0.11 + (idx % 12) * 0.01, 2)},
                    "symmetry_lock": {"type": "bool", "default": True},
                    "clothing_protection": {"type": "bool", "default": True},
                },
                "dependencies": [guard_dep],
            }
        )

    # 4. Face Sculpting Templates (89 items -> total 90 in face_sculpting)
    face_actions = [
        ("JAWLINE_SCULPT", "流畅折角下颌线收紧与双下巴消除", ["下颌线", "双下巴", "瘦脸", "清晰轮廓", "jawline", "chin"]),
        ("ZYGOMA_SMOOTH", "颧骨内推柔和与太阳穴饱满流畅", ["颧骨", "太阳穴", "脸型流畅", "柔和轮廓", "cheekbone", "temple"]),
        ("CRANIAL_HAIR", "高颅顶蓬松与发际线绒毛自然修补", ["高颅顶", "发际线", "头包脸", "发量", "hairline", "cranial"]),
        ("EYE_BRIGHT", "眼型微调放大与卧蚕神采立体精修", ["大眼", "眼神", "卧蚕", "眼尾提拉", "eyes", "gaze"]),
        ("NOSE_MIDFACE", "山根鼻翼精致微缩与幼态中庭比例", ["瘦鼻", "鼻梁", "山根", "中庭", "人中", "nose", "midface"]),
    ]
    for idx in range(1, 90):
        code, base_name, kws = face_actions[(idx - 1) % len(face_actions)]
        style_tag = ["原生骨相", "电影写真", "清冷高级感"][(idx - 1) % 3]
        tid = f"T_FACE_SCULPT_{idx:03d}"
        templates.append(
            {
                "template_id": tid,
                "name": f"{style_tag}·{base_name} #{idx:02d}",
                "category": "face_sculpting",
                "keywords": kws + [style_tag, code.lower(), "五官精修"],
                "target_scope": "single_person",
                "slot_definitions": {
                    "intensity": {"type": "float", "default": round(0.10 + (idx % 10) * 0.01, 2)},
                    "neck_transition_smooth": {"type": "bool", "default": True},
                    "preserve_expression": {"type": "bool", "default": True},
                },
                "dependencies": [],
            }
        )

    # 5. Skin & Lighting Templates (89 items -> total 90 in skin_lighting), enriched with ATBDraw-prompts.csv
    skin_actions = [
        ("DUAL_FREQ_SKIN", "双频分离毛孔肌理保留与瑕疵痘印净除", ["磨皮", "祛痘", "毛孔", "原生肤质", "skin_texture", "blemish"]),
        ("TEAR_NASOLABIAL", "法令纹泪沟木偶纹光影柔焦淡化", ["法令纹", "泪沟", "黑眼圈", "去疲态", "nasolabial", "dark_circle"]),
        ("CREAM_COMPLEXION", "冷白皮通透匀色与脖子色差自然对齐", ["美白", "冷白皮", "通透", "脖子色差", "肤色均匀", "whitening"]),
        ("REMBRANDT_GLOW", "杂志级立体追光与面部T区高光重塑", ["高光", "追光", "立体光影", "蝴蝶光", "伦勃朗光", "lighting", "glow"]),
        ("CATCHLIGHT_MATTE", "眼神光晶莹增强与油光区域柔雾控油", ["眼神光", "去油光", "哑光奶油肌", "清透感", "catchlight", "matte"]),
    ]
    for idx in range(1, 90):
        code, base_name, kws = skin_actions[(idx - 1) % len(skin_actions)]
        csv_ref = csv_snippets[(idx - 1) % len(csv_snippets)]["title"][:28] if csv_snippets else "Studio Editorial"
        tid = f"T_SKIN_LIGHT_{idx:03d}"
        templates.append(
            {
                "template_id": tid,
                "name": f"{base_name} ({csv_ref}) #{idx:02d}",
                "category": "skin_lighting",
                "keywords": kws + [code.lower(), "质感光影", csv_ref.lower()],
                "target_scope": "single_person",
                "slot_definitions": {
                    "smooth_strength": {"type": "float", "default": round(0.35 + (idx % 15) * 0.01, 2)},
                    "preserve_skin_texture": {"type": "bool", "default": True},
                    "protect_catchlights": {"type": "bool", "default": True},
                    "ambient_color_match": {"type": "bool", "default": True},
                },
                "dependencies": [],
            }
        )

    return templates


def validate_templates_file(json_path: Path) -> int:
    if not json_path.is_file():
        print(f"[ERROR] File not found: {json_path}", file=sys.stderr)
        return 1

    raw_data = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(raw_data, list):
        print("[ERROR] Root JSON structure must be a list of TemplateMetadata objects.", file=sys.stderr)
        return 1

    if len(raw_data) < 300 or len(raw_data) > 500:
        print(f"[ERROR] Expected between 300 and 500 templates, found {len(raw_data)}.", file=sys.stderr)
        return 1

    seen_ids = set()
    validated: List[TemplateMetadata] = []
    categories: Dict[str, int] = {}

    for idx, item in enumerate(raw_data):
        try:
            model = TemplateMetadata.model_validate(item)
        except Exception as exc:
            print(f"[ERROR] Schema validation failed at index {idx}: {exc}", file=sys.stderr)
            return 1

        if model.template_id in seen_ids:
            print(f"[ERROR] Duplicate template_id detected: {model.template_id}", file=sys.stderr)
            return 1
        seen_ids.add(model.template_id)

        if not model.keywords or not model.slot_definitions:
            print(f"[ERROR] Template {model.template_id} has empty keywords or slot_definitions.", file=sys.stderr)
            return 1

        categories[model.category] = categories.get(model.category, 0) + 1
        validated.append(model)

    # Verify all dependencies reference existing template IDs
    for model in validated:
        for dep in model.dependencies:
            if dep not in seen_ids:
                print(
                    f"[ERROR] Template {model.template_id} references unknown dependency {dep}",
                    file=sys.stderr,
                )
                return 1

    # Verify SQLite bulk import via TemplateStore
    store = TemplateStore(":memory:")
    inserted = store.upsert_templates("draw", validated)
    store.close()
    if inserted != len(validated):
        print(f"[ERROR] SQLite upsert mismatch: expected {len(validated)}, got {inserted}", file=sys.stderr)
        return 1

    print(
        f"[OK] Validated {len(validated)} templates across {len(categories)} categories "
        f"({categories}) and imported into SQLite with 0 errors."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate or generate ATBMind-Draw seed templates.")
    parser.add_argument("json_path", type=Path, help="Path to seed_templates.json")
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate seed_templates.json before running validation",
    )
    args = parser.parse_args()

    if args.generate or not args.json_path.is_file():
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        seed_data = generate_seed_templates()
        args.json_path.write_text(json.dumps(seed_data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[GENERATED] Wrote {len(seed_data)} seed templates to {args.json_path}")

    return validate_templates_file(args.json_path)


if __name__ == "__main__":
    sys.exit(main())
