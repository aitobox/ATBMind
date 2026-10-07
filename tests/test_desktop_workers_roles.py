import pytest
from unittest.mock import MagicMock
from pathlib import Path
from apps.atbmind_desktop.workers import GenerationWorker
from atbmind_core.roles.team import RobotTeam

def test_generation_worker_role_attributes():
    worker = GenerationWorker(
        session_id="test_sess",
        prompt="测试提示词",
        active_role_id="draw_expert",
    )
    assert worker.session_id == "test_sess"
    assert worker.active_role_id == "draw_expert"
    # Backwards compatibility check
    assert worker.active_plugin_id == "draw_expert"

def test_generation_worker_team_setup():
    worker = GenerationWorker(
        session_id="test_sess",
        prompt="测试团队设置",
        use_harness=True,
    )
    assert worker.use_harness is True
