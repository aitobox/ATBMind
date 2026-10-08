"""
ATBMind Team Job Tracker & In-Flight Job Management.
Maintains in-memory thread-safe state tracking for team dispatch jobs and roster locks.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("atbmind.roles.jobs")


class TeamJobStatus(str, Enum):
    """Lifecycle statuses for team jobs."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TeamJob:
    """Represents a discrete in-flight task delegated to a team specialist."""

    job_id: str
    role_id: str
    task_description: str
    team_id: str = "default"
    status: TeamJobStatus = TeamJobStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        """Returns True if the job is either pending or actively executing."""
        return self.status in (TeamJobStatus.PENDING, TeamJobStatus.RUNNING)

    @property
    def is_terminal(self) -> bool:
        """Returns True if the job has ended (completed, failed, or cancelled)."""
        return self.status in (
            TeamJobStatus.COMPLETED,
            TeamJobStatus.FAILED,
            TeamJobStatus.CANCELLED,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts job state to a serializable dictionary."""
        return {
            "job_id": self.job_id,
            "role_id": self.role_id,
            "team_id": self.team_id,
            "task_description": self.task_description,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metadata": dict(self.metadata),
        }


class TeamJobTracker:
    """
    In-process thread-safe manager for tracking in-flight specialist jobs and roster locks.
    Guarantees synchronization and atomic state transitions across concurrent worker threads.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._jobs: Dict[str, TeamJob] = {}
        # Interoperability pair counters: (team_id, member_id) -> count
        self._counts: Dict[tuple[str, str], int] = {}
        # Job-to-pair mapping for explicit roster locks: job_id -> (team_id, member_id)
        self._roster_jobs: Dict[str, tuple[str, str]] = {}

    def submit_job(
        self,
        role_id: str,
        task_description: str,
        job_id: Optional[str] = None,
        team_id: Optional[str] = "default",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TeamJob:
        """
        Registers a new specialist job in PENDING status.
        Raises ValueError if a job with the specified job_id already exists.
        """
        assigned_id = job_id or f"job_{uuid.uuid4().hex[:12]}"
        effective_team = team_id or "default"

        with self._lock:
            if assigned_id in self._jobs:
                raise ValueError(f"Job with id '{assigned_id}' already exists")

            job = TeamJob(
                job_id=assigned_id,
                role_id=role_id,
                task_description=task_description,
                team_id=effective_team,
                status=TeamJobStatus.PENDING,
                metadata=metadata or {},
            )
            self._jobs[assigned_id] = job
            # Also register roster lock for this job
            self._roster_jobs[assigned_id] = (effective_team, role_id)
            return job

    def start_job(self, job_id: str) -> TeamJob:
        """
        Transitions a job from PENDING to RUNNING status.
        Raises KeyError if job not found, or ValueError if not in PENDING state.
        """
        with self._lock:
            if job_id not in self._jobs:
                raise KeyError(f"Job '{job_id}' not found")
            job = self._jobs[job_id]
            if job.status != TeamJobStatus.PENDING:
                raise ValueError(
                    f"Cannot start job '{job_id}': status is '{job.status.value}', expected 'pending'"
                )
            job.status = TeamJobStatus.RUNNING
            job.started_at = time.time()
            return job

    def complete_job(self, job_id: str, result: str = "") -> TeamJob:
        """
        Marks an in-flight job as COMPLETED and releases associated locks.
        Raises KeyError if job not found, or ValueError if already terminal.
        """
        with self._lock:
            if job_id not in self._jobs:
                raise KeyError(f"Job '{job_id}' not found")
            job = self._jobs[job_id]
            if job.is_terminal:
                raise ValueError(
                    f"Cannot complete already terminal job '{job_id}' with status '{job.status.value}'"
                )
            job.status = TeamJobStatus.COMPLETED
            job.result = result
            job.completed_at = time.time()
            self._roster_jobs.pop(job_id, None)
            return job

    def fail_job(self, job_id: str, error: str = "") -> TeamJob:
        """
        Marks an in-flight job as FAILED and releases associated locks.
        Raises KeyError if job not found, or ValueError if already terminal.
        """
        with self._lock:
            if job_id not in self._jobs:
                raise KeyError(f"Job '{job_id}' not found")
            job = self._jobs[job_id]
            if job.is_terminal:
                raise ValueError(
                    f"Cannot fail already terminal job '{job_id}' with status '{job.status.value}'"
                )
            job.status = TeamJobStatus.FAILED
            job.error = error
            job.completed_at = time.time()
            self._roster_jobs.pop(job_id, None)
            return job

    def cancel_job(self, job_id: str, reason: str = "") -> TeamJob:
        """
        Cancels an in-flight job and releases associated locks.
        Raises KeyError if job not found, or ValueError if already terminal.
        """
        with self._lock:
            if job_id not in self._jobs:
                raise KeyError(f"Job '{job_id}' not found")
            job = self._jobs[job_id]
            if job.is_terminal:
                raise ValueError(
                    f"Cannot cancel already terminal job '{job_id}' with status '{job.status.value}'"
                )
            job.status = TeamJobStatus.CANCELLED
            job.error = reason
            job.completed_at = time.time()
            self._roster_jobs.pop(job_id, None)
            return job

    def get_job(self, job_id: str) -> Optional[TeamJob]:
        """Retrieves a job by its unique ID, or None if not found."""
        with self._lock:
            return self._jobs.get(job_id)

    def list_active_jobs(
        self,
        role_id: Optional[str] = None,
        team_id: Optional[str] = None,
    ) -> List[TeamJob]:
        """
        Returns a list of all jobs currently in PENDING or RUNNING status,
        optionally filtered by role_id and/or team_id.
        """
        with self._lock:
            active = []
            for job in self._jobs.values():
                if not job.is_active:
                    continue
                if role_id and job.role_id != role_id:
                    continue
                if team_id and job.team_id != team_id:
                    continue
                active.append(job)
            return active

    def has_active_jobs(
        self,
        role_id: Optional[str] = None,
        team_id: Optional[str] = None,
    ) -> bool:
        """Returns True if there is at least one active job matching the criteria."""
        with self._lock:
            for job in self._jobs.values():
                if not job.is_active:
                    continue
                if role_id and job.role_id != role_id:
                    continue
                if team_id and job.team_id != team_id:
                    continue
                return True
            return False

    def is_role_busy(self, role_id: str) -> bool:
        """Checks if the given specialist role has any in-flight jobs or roster locks."""
        with self._lock:
            if self.has_active_jobs(role_id=role_id):
                return True
            return self.is_member_busy(role_id)

    def busy_role_ids(self, team_id: Optional[str] = None) -> Set[str]:
        """Returns a set of all role IDs that currently have active jobs or roster locks."""
        with self._lock:
            busy = set()
            for job in self._jobs.values():
                if job.is_active:
                    if team_id is None or job.team_id == team_id:
                        busy.add(job.role_id)
            if team_id:
                busy.update(self.busy_member_ids(team_id))
            else:
                for (_, member), count in self._counts.items():
                    if count > 0:
                        busy.add(member)
                for _, member in self._roster_jobs.values():
                    busy.add(member)
            return busy

    # --- Octop Roster Lock Interoperability Methods ---

    def begin(
        self,
        team_agent_id: str,
        member_agent_id: str,
        job_id: Optional[str] = None,
    ) -> None:
        """Acquires a roster lock for a team-member dispatch pair."""
        key = (team_agent_id, member_agent_id)
        with self._lock:
            if job_id:
                if job_id in self._roster_jobs:
                    return
                self._roster_jobs[job_id] = key
                return
            self._counts[key] = self._counts.get(key, 0) + 1

    def end(
        self,
        team_agent_id: str,
        member_agent_id: str,
        job_id: Optional[str] = None,
    ) -> None:
        """Releases a roster lock for a team-member dispatch pair."""
        key = (team_agent_id, member_agent_id)
        with self._lock:
            if job_id:
                self._roster_jobs.pop(job_id, None)
                return
            current = self._counts.get(key, 0) - 1
            if current <= 0:
                self._counts.pop(key, None)
            else:
                self._counts[key] = current

    def is_busy(self, team_agent_id: str, member_agent_id: str) -> bool:
        """Returns True if the specific (team, member) pair is currently locked."""
        key = (team_agent_id, member_agent_id)
        with self._lock:
            if self._counts.get(key, 0) > 0:
                return True
            return any(pair == key for pair in self._roster_jobs.values())

    def is_member_busy(self, member_agent_id: str) -> bool:
        """Returns True if the member has any active roster locks across any team."""
        with self._lock:
            if any(
                count > 0 and member == member_agent_id
                for (_, member), count in self._counts.items()
            ):
                return True
            return any(member == member_agent_id for (_, member) in self._roster_jobs.values())

    def busy_member_ids(self, team_agent_id: str) -> Set[str]:
        """Returns the set of member role IDs locked under the specified team."""
        with self._lock:
            busy = {
                member
                for (team, member), count in self._counts.items()
                if team == team_agent_id and count > 0
            }
            busy.update(
                member for team, member in self._roster_jobs.values() if team == team_agent_id
            )
            return busy
