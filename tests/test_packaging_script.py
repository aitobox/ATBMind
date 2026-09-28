import os
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]


def test_build_nuitka_script_executable_and_dry_run():
    """Verify scripts/build_nuitka.sh exists, has executable permissions, and succeeds in dry-run mode."""
    script_path = ROOT_DIR / "scripts" / "build_nuitka.sh"
    assert script_path.is_file()
    assert os.access(script_path, os.X_OK), "scripts/build_nuitka.sh must be executable"

    res = subprocess.run(
        ["bash", str(script_path), "--dry-run"],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "[DRY-RUN] Verified dependencies and build targets." in res.stdout
    assert "--standalone" in res.stdout
    assert "--enable-plugin=pyside6" in res.stdout


def test_atb_draw_desktop_version_cli():
    """Verify apps/atb_draw_desktop/main.py --version outputs version and exits 0."""
    entrypoint = ROOT_DIR / "apps" / "atb_draw_desktop" / "main.py"
    res = subprocess.run(
        [sys.executable, str(entrypoint), "--version"],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "ATBDraw 0.1.0" in res.stdout


def test_packaging_guide_documentation_exists():
    """Verify docs/packaging_guide.md is present and documents smoke test checklist."""
    doc_path = ROOT_DIR / "docs" / "packaging_guide.md"
    assert doc_path.is_file()
    content = doc_path.read_text(encoding="utf-8")
    assert "Nuitka" in content
    assert "--version" in content
    assert "冒烟测试" in content
