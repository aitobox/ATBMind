import json
from pathlib import Path

from atbmind_core.storage.db import TemplateStore
from atbmind_core.storage.schemas import TemplateMetadata
from skills.image_generation.tools import SEED_TEMPLATES_PATH
from scripts.validate_templates import validate_templates_file


def _load_templates() -> list[TemplateMetadata]:
    with open(SEED_TEMPLATES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [TemplateMetadata.model_validate(item) for item in data]


def test_seed_templates_validation_and_category_distribution():
    """Verify seed_templates.json passes validation script and contains 300~500 templates across 4 categories."""
    assert SEED_TEMPLATES_PATH.is_file()
    exit_code = validate_templates_file(SEED_TEMPLATES_PATH)
    assert exit_code == 0

    templates = _load_templates()
    assert 300 <= len(templates) <= 500

    categories = {t.category for t in templates}
    assert {"body_shaping", "face_sculpting", "skin_lighting", "cloth_background"}.issubset(categories)


def test_seed_templates_sqlite_import_and_search():
    """Verify all 360 seed templates import cleanly into TemplateStore and support bucketed search."""
    templates = _load_templates()

    store = TemplateStore(":memory:")
    inserted = store.upsert_templates("draw", templates)
    assert inserted == len(templates)

    waist_tpls = store.query_templates("draw", category="body_shaping", keyword="瘦腰")
    assert len(waist_tpls) >= 10

    jaw_tpls = store.query_templates("draw", category="face_sculpting", keyword="下颌线")
    assert len(jaw_tpls) >= 10
    store.close()
