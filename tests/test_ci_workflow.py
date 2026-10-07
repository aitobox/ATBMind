from pathlib import Path
import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT_DIR / ".github" / "workflows" / "test.yml"


def test_workflow_file_exists_and_valid_yaml():
    assert WORKFLOW_PATH.is_file(), ".github/workflows/test.yml does not exist"
    data = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    assert data is not None
    assert data.get("name") == "Tests"


def test_workflow_triggers_and_concurrency():
    data = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    # Triggers
    on_clause = data.get("on") or data.get(True) or {}
    assert "push" in on_clause
    assert "pull_request" in on_clause
    assert "workflow_dispatch" in on_clause
    assert "main" in on_clause["push"]["branches"]
    assert "main" in on_clause["pull_request"]["branches"]

    # Concurrency
    concurrency = data.get("concurrency", {})
    assert concurrency.get("cancel-in-progress") is True


def test_workflow_matrix_and_offscreen():
    data = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    jobs = data.get("jobs", {})
    assert "pytest" in jobs
    pytest_job = jobs["pytest"]

    matrix = pytest_job.get("strategy", {}).get("matrix", {})
    assert "ubuntu-latest" in matrix.get("os", [])
    assert "macos-latest" in matrix.get("os", [])
    assert "3.12" in matrix.get("python-version", [])

    # Check test step environment
    steps = pytest_job.get("steps", [])
    test_step = next((s for s in steps if "Run pytest" in s.get("name", "")), None)
    assert test_step is not None, "Run pytest step not found"
    assert test_step.get("env", {}).get("QT_QPA_PLATFORM") == "offscreen"
