import concurrent.futures
import threading
import time
import pytest

from atbmind_core.roles.jobs import (
    TeamJob,
    TeamJobStatus,
    TeamJobTracker,
)


def test_team_job_status_enum():
    assert TeamJobStatus.PENDING == "pending"
    assert TeamJobStatus.RUNNING == "running"
    assert TeamJobStatus.COMPLETED == "completed"
    assert TeamJobStatus.FAILED == "failed"
    assert TeamJobStatus.CANCELLED == "cancelled"


def test_team_job_lifecycle_success():
    tracker = TeamJobTracker()

    # 1. Submit
    job = tracker.submit_job(
        role_id="coder",
        task_description="Implement unit tests",
        team_id="team_alpha",
    )
    assert job.status == TeamJobStatus.PENDING
    assert job.role_id == "coder"
    assert job.team_id == "team_alpha"
    assert job.created_at > 0
    assert job.started_at is None
    assert job.completed_at is None
    assert tracker.has_active_jobs() is True
    assert tracker.is_role_busy("coder") is True
    assert tracker.is_role_busy("designer") is False
    assert "coder" in tracker.busy_role_ids()

    # 2. Start
    started_job = tracker.start_job(job.job_id)
    assert started_job.status == TeamJobStatus.RUNNING
    assert started_job.started_at is not None
    assert tracker.is_role_busy("coder") is True

    # 3. Complete
    completed_job = tracker.complete_job(job.job_id, result="All tests pass")
    assert completed_job.status == TeamJobStatus.COMPLETED
    assert completed_job.result == "All tests pass"
    assert completed_job.completed_at is not None
    assert tracker.has_active_jobs() is False
    assert tracker.is_role_busy("coder") is False
    assert len(tracker.busy_role_ids()) == 0


def test_team_job_failure_lifecycle():
    tracker = TeamJobTracker()
    job = tracker.submit_job(role_id="reviewer", task_description="Audit code")
    tracker.start_job(job.job_id)

    failed_job = tracker.fail_job(job.job_id, error="Syntax error detected")
    assert failed_job.status == TeamJobStatus.FAILED
    assert failed_job.error == "Syntax error detected"
    assert failed_job.completed_at is not None
    assert tracker.has_active_jobs() is False


def test_team_job_cancellation():
    tracker = TeamJobTracker()
    job = tracker.submit_job(role_id="analyst", task_description="Long running query")
    cancelled_job = tracker.cancel_job(job.job_id, reason="User cancelled request")

    assert cancelled_job.status == TeamJobStatus.CANCELLED
    assert cancelled_job.error == "User cancelled request"
    assert tracker.has_active_jobs() is False


def test_team_job_invalid_transitions():
    tracker = TeamJobTracker()
    job = tracker.submit_job(role_id="designer", task_description="Draw avatar")
    tracker.start_job(job.job_id)
    tracker.complete_job(job.job_id, result="Done")

    # Cannot start completed job
    with pytest.raises(ValueError):
        tracker.start_job(job.job_id)

    # Cannot complete again
    with pytest.raises(ValueError):
        tracker.complete_job(job.job_id, result="Again")

    # Cannot fail completed job
    with pytest.raises(ValueError):
        tracker.fail_job(job.job_id, error="Too late")

    # Cannot cancel completed job
    with pytest.raises(ValueError):
        tracker.cancel_job(job.job_id, reason="Too late")

    # Non-existent job
    with pytest.raises(KeyError):
        tracker.start_job("non-existent-id")


def test_list_active_jobs_and_filtering():
    tracker = TeamJobTracker()

    j1 = tracker.submit_job(role_id="coder", task_description="Task 1", team_id="team_a")
    j2 = tracker.submit_job(role_id="designer", task_description="Task 2", team_id="team_a")
    j3 = tracker.submit_job(role_id="coder", task_description="Task 3", team_id="team_b")

    tracker.start_job(j1.job_id)
    tracker.start_job(j2.job_id)

    # Filter all active
    active = tracker.list_active_jobs()
    assert len(active) == 3

    # Filter by role
    coder_active = tracker.list_active_jobs(role_id="coder")
    assert len(coder_active) == 2

    # Filter by team
    team_a_active = tracker.list_active_jobs(team_id="team_a")
    assert len(team_a_active) == 2

    # Filter by both
    team_b_coder = tracker.list_active_jobs(role_id="coder", team_id="team_b")
    assert len(team_b_coder) == 1
    assert team_b_coder[0].job_id == j3.job_id

    # Complete j1
    tracker.complete_job(j1.job_id, result="Done")
    coder_active_after = tracker.list_active_jobs(role_id="coder")
    assert len(coder_active_after) == 1
    assert coder_active_after[0].job_id == j3.job_id


def test_roster_lock_interoperability():
    tracker = TeamJobTracker()

    # Begin with explicit job_id
    tracker.begin("coordinator", "coder", job_id="job_001")
    assert tracker.is_busy("coordinator", "coder") is True
    assert tracker.is_member_busy("coder") is True
    assert "coder" in tracker.busy_member_ids("coordinator")

    # Idempotent begin
    tracker.begin("coordinator", "coder", job_id="job_001")
    assert tracker.is_member_busy("coder") is True

    # End
    tracker.end("coordinator", "coder", job_id="job_001")
    assert tracker.is_busy("coordinator", "coder") is False
    assert tracker.is_member_busy("coder") is False

    # Anonymous begin without job_id (ref count)
    tracker.begin("coordinator", "designer")
    tracker.begin("coordinator", "designer")
    assert tracker.is_busy("coordinator", "designer") is True
    tracker.end("coordinator", "designer")
    assert tracker.is_busy("coordinator", "designer") is True
    tracker.end("coordinator", "designer")
    assert tracker.is_busy("coordinator", "designer") is False


def test_concurrent_job_tracking():
    tracker = TeamJobTracker()
    num_threads = 20
    jobs_per_thread = 10

    def worker(worker_id: int):
        role_id = f"worker_{worker_id % 4}"
        for i in range(jobs_per_thread):
            job = tracker.submit_job(role_id=role_id, task_description=f"Task {i}")
            tracker.start_job(job.job_id)
            time.sleep(0.001)
            tracker.complete_job(job.job_id, result=f"Done {i}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, i) for i in range(num_threads)]
        concurrent.futures.wait(futures)

    assert tracker.has_active_jobs() is False
    assert len(tracker.list_active_jobs()) == 0
    assert len(tracker.busy_role_ids()) == 0
