from pathlib import Path
import time

from atbmind_core.plugins.schemas import TemplateMetadata
from atbmind_core.storage.db import TemplateStore


def test_sqlite_in_memory_crud_and_filtering():
    """Verify CRUD operations and multi-dimensional filtering in :memory: mode."""
    store = TemplateStore(":memory:")
    templates = [
        TemplateMetadata(
            template_id="T_001",
            name="瘦腰塑形",
            category="body_shaping",
            keywords=["瘦腰", "塑形", "waist"],
            target_scope="single_person",
            slot_definitions={"intensity": {"type": "float", "default": 0.15}},
            dependencies=[],
        ),
        TemplateMetadata(
            template_id="T_002",
            name="服装边缘锁定",
            category="body_shaping",
            keywords=["衣服", "防变形", "clothing"],
            target_scope="single_person",
            slot_definitions={"preserve_ratio": {"type": "float", "default": 0.85}},
            dependencies=["T_001"],
        ),
        TemplateMetadata(
            template_id="T_003",
            name="双频通透磨皮",
            category="skin_retouching",
            keywords=["磨皮", "祛痘", "skin"],
            target_scope="face_only",
            slot_definitions={"smooth": {"type": "float", "default": 0.45}},
            dependencies=[],
        ),
    ]

    inserted = store.upsert_templates("draw", templates)
    assert inserted == 3
    assert store.count_templates("draw") == 3

    # Query by category
    body_tpls = store.query_templates("draw", category="body_shaping")
    assert len(body_tpls) == 2
    assert {t.template_id for t in body_tpls} == {"T_001", "T_002"}

    # Query by target_scope
    face_tpls = store.query_templates("draw", target_scope="face_only")
    assert len(face_tpls) == 1
    assert face_tpls[0].template_id == "T_003"

    # Query by keyword
    kw_tpls = store.query_templates("draw", keyword="祛痘")
    assert len(kw_tpls) == 1
    assert kw_tpls[0].template_id == "T_003"

    # Upsert update existing template
    updated_t1 = templates[0].model_copy(update={"name": "高级瘦腰塑形 v2"})
    store.upsert_templates("draw", [updated_t1])
    fetched = store.get_template("draw", "T_001")
    assert fetched is not None
    assert fetched.name == "高级瘦腰塑形 v2"
    assert store.count_templates("draw") == 3

    # Delete template
    assert store.delete_template("draw", "T_002") is True
    assert store.get_template("draw", "T_002") is None
    assert store.count_templates("draw") == 2
    store.close()


def test_sqlite_file_persistence_and_bulk_performance(tmp_path: Path):
    """Verify file persistence and < 100ms bulk upsert for 1,000 templates."""
    db_path = tmp_path / "templates_test.db"
    store = TemplateStore(db_path)

    bulk_templates = [
        TemplateMetadata(
            template_id=f"T_BULK_{i:04d}",
            name=f"测试模板 {i}",
            category="body_shaping" if i % 2 == 0 else "skin_retouching",
            keywords=[f"kw_{i}", "portrait"],
            target_scope="single_person",
            slot_definitions={"strength": {"type": "float", "default": 0.12}},
            dependencies=[] if i == 0 else [f"T_BULK_{i - 1:04d}"],
        )
        for i in range(1000)
    ]

    t0 = time.perf_counter()
    count = store.upsert_templates("draw", bulk_templates)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert count == 1000
    assert elapsed_ms < 100.0, f"Bulk upsert took {elapsed_ms:.2f}ms, expected < 100ms"
    store.close()

    # Re-open from disk to verify persistence
    reopened = TemplateStore(db_path)
    assert reopened.count_templates("draw") == 1000
    shaping = reopened.query_templates("draw", category="body_shaping")
    assert len(shaping) == 500
    reopened.close()
