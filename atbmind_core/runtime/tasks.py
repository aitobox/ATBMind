"""Background Task Manager, Persistent Terminals, and Scheduler for ATBMind Runtime.

Provides adaptive synchronous/asynchronous shell execution, process tree management
with process group cleanup, persistent terminal state sharing, and timer/cron scheduling.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from enum import Enum
import logging
import os
from pathlib import Path
import signal
from typing import Any, Dict, List, Optional, Set, Union
import uuid

from pydantic import BaseModel, Field

from .event_bus import (
    AsyncEventBus,
    RuntimeEvent,
    TaskOutputEvent,
    TaskStatusChangedEvent,
    TimerFiredEvent,
)

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Lifecycle status of a background shell task."""

    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    KILLED = "killed"


class BackgroundTask(BaseModel):
    """State descriptor for a managed background task."""

    task_id: str
    command: str
    cwd: str
    status: TaskStatus = TaskStatus.RUNNING
    log_file: Path
    exit_code: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.now)
    is_daemon: bool = False
    terminal_id: Optional[str] = None

    model_config = {"arbitrary_types_allowed": True}


class PersistentTerminal(BaseModel):
    """Descriptor for a persistent terminal session sharing environment variables."""

    terminal_id: str
    env_file: Path
    created_at: datetime = Field(default_factory=datetime.now)


class ScheduledTimer(BaseModel):
    """Descriptor for a scheduled one-shot timer or recurring cron job."""

    timer_id: str
    prompt: str
    is_cron: bool = False
    cron_expr: Optional[str] = None
    max_iterations: Optional[int] = None
    duration_s: Optional[float] = None
    condition: str = "never"
    status: str = "running"  # "running", "done", "cancelled", "killed", "failed"
    created_at: datetime = Field(default_factory=datetime.now)


# ============================================================================
# Cron Parsing & Matching Helpers (Pure Python / Zero Heavy Dependencies)
# ============================================================================

def parse_cron_field(field_str: str, min_val: int, max_val: int) -> Set[int]:
    """Parse a single 5-field cron component into a set of matching integer values.

    Supports: '*', '*/N', 'N', 'N,M', 'N-M', 'N-M/S'.
    """
    field_str = field_str.strip()
    if not field_str:
        raise ValueError("Empty cron field")

    result: Set[int] = set()
    parts = field_str.split(",")
    for part in parts:
        part = part.strip()
        if part == "*":
            result.update(range(min_val, max_val + 1))
        elif part.startswith("*/"):
            step = int(part[2:])
            if step <= 0:
                raise ValueError(f"Invalid step value: {part}")
            for v in range(min_val, max_val + 1):
                if (v - min_val) % step == 0:
                    result.add(v)
        elif "-" in part:
            if "/" in part:
                range_part, step_part = part.split("/", 1)
                start_s, end_s = range_part.split("-", 1)
                start, end = int(start_s), int(end_s)
                step = int(step_part)
            else:
                start_s, end_s = part.split("-", 1)
                start, end = int(start_s), int(end_s)
                step = 1
            if start > end or step <= 0:
                raise ValueError(f"Invalid cron range: {part}")
            for v in range(start, end + 1):
                if (v - start) % step == 0 and min_val <= v <= max_val:
                    result.add(v)
        else:
            val = int(part)
            # For weekday, 7 is standardly accepted as Sunday (0)
            if max_val == 6 and min_val == 0 and val == 7:
                val = 0
            elif val < min_val or val > max_val:
                raise ValueError(f"Cron value {val} out of bounds [{min_val}, {max_val}]")
            result.add(val)
    return result


def cron_match(cron_expr: str, dt: datetime) -> bool:
    """Check whether a given datetime matches a 5-field cron expression."""
    fields = cron_expr.strip().split()
    if len(fields) != 5:
        raise ValueError(f"Invalid cron expression (must have 5 fields): '{cron_expr}'")
    m_field, h_field, dom_field, mon_field, dow_field = fields
    minutes = parse_cron_field(m_field, 0, 59)
    hours = parse_cron_field(h_field, 0, 23)
    doms = parse_cron_field(dom_field, 1, 31)
    months = parse_cron_field(mon_field, 1, 12)
    # Python weekday(): Monday is 0, Sunday is 6.
    # Standard cron: Sunday is 0 (or 7), Monday is 1 ... Saturday is 6.
    # cron_dow: (dt.weekday() + 1) % 7
    dows = parse_cron_field(dow_field, 0, 6)
    cron_dow = (dt.weekday() + 1) % 7

    return (
        dt.minute in minutes
        and dt.hour in hours
        and dt.day in doms
        and dt.month in months
        and cron_dow in dows
    )


def get_next_cron_run(cron_expr: str, base_time: Optional[datetime] = None) -> datetime:
    """Calculate the next matching datetime for a 5-field cron expression."""
    base = base_time or datetime.now()
    # Advance to the beginning of the next minute
    candidate = base.replace(second=0, microsecond=0) + timedelta(minutes=1)
    # Search up to 366 days ahead
    max_minutes = 366 * 24 * 60
    for _ in range(max_minutes):
        if cron_match(cron_expr, candidate):
            return candidate
        candidate += timedelta(minutes=1)
    raise ValueError(f"No matching cron time found within 1 year for '{cron_expr}'")


# ============================================================================
# TaskManager
# ============================================================================

class TaskManager:
    """Central engine for command execution, persistent terminals, and scheduling."""

    def __init__(
        self,
        event_bus: Optional[AsyncEventBus] = None,
        log_dir: Optional[Union[str, Path]] = None,
    ) -> None:
        self.event_bus = event_bus or AsyncEventBus()
        self.log_dir = Path(log_dir) if log_dir else Path("data/tasks")
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self._tasks: Dict[str, BackgroundTask] = {}
        self._processes: Dict[str, asyncio.subprocess.Process] = {}
        self._background_jobs: Dict[str, asyncio.Task[Any]] = {}

        self._terminals: Dict[str, PersistentTerminal] = {}
        self._timers: Dict[str, ScheduledTimer] = {}
        self._timer_tasks: Dict[str, asyncio.Task[Any]] = {}

    # ------------------------------------------------------------------------
    # Shell Execution (run_command)
    # ------------------------------------------------------------------------

    async def run_command(
        self,
        command: Optional[str] = None,
        cwd: Optional[str] = None,
        wait_ms_before_async: Optional[int] = None,
        is_daemon: Optional[bool] = None,
        run_persistent: Optional[bool] = None,
        requested_terminal_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Execute a shell command with adaptive synchronous/asynchronous transition.

        - If command completes within wait_ms_before_async: returns output synchronously.
        - If command exceeds wait_ms_before_async: smoothly transitions to background,
          streaming output to persistent log file and returning task_id immediately.
        """
        cmd = command or kwargs.get("cmd") or kwargs.get("CommandLine") or ""
        exec_cwd = cwd or kwargs.get("Cwd") or os.getcwd()
        wait_ms = (
            wait_ms_before_async
            if wait_ms_before_async is not None
            else kwargs.get("wait_ms", kwargs.get("WaitMsBeforeAsync", 5000))
        )
        daemon_flag = (
            is_daemon
            if is_daemon is not None
            else kwargs.get("IsDaemon", False)
        )
        persistent_flag = (
            run_persistent
            if run_persistent is not None
            else kwargs.get("RunPersistent", False)
        )
        req_term_id = (
            requested_terminal_id
            or kwargs.get("RequestedTerminalID")
        )

        if not cmd.strip():
            return {
                "is_async": False,
                "task_id": "",
                "output": "",
                "exit_code": 1,
                "status": TaskStatus.FAILED.value,
                "error": "Empty command string",
            }

        # Handle persistent terminal binding
        term_id: Optional[str] = None
        cmd_to_execute = cmd
        if persistent_flag or req_term_id:
            if req_term_id:
                term_id = req_term_id
                if term_id not in self._terminals:
                    self._terminals[term_id] = PersistentTerminal(
                        terminal_id=term_id,
                        env_file=self.log_dir / f"{term_id}.env",
                    )
            else:
                term_id = f"term-{uuid.uuid4().hex[:8]}"
                self._terminals[term_id] = PersistentTerminal(
                    terminal_id=term_id,
                    env_file=self.log_dir / f"{term_id}.env",
                )

            env_path = str(self._terminals[term_id].env_file.resolve())
            cmd_to_execute = (
                f'if [ -f "{env_path}" ]; then source "{env_path}" 2>/dev/null || true; fi\n'
                f"{cmd}\n"
                f"__ATBMIND_RET__=$?\n"
                f'export -p > "{env_path}" 2>/dev/null || true\n'
                f"exit $__ATBMIND_RET__"
            )

        task_id = f"task-{uuid.uuid4().hex[:8]}"
        log_file = self.log_dir / f"{task_id}.log"

        # Create subprocess with process group isolation
        preexec = os.setsid if hasattr(os, "setsid") else None

        process = await asyncio.create_subprocess_shell(
            cmd_to_execute,
            cwd=exec_cwd,
            executable="/bin/bash" if os.path.exists("/bin/bash") else None,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            preexec_fn=preexec,
        )

        task_record = BackgroundTask(
            task_id=task_id,
            command=cmd,
            cwd=exec_cwd,
            status=TaskStatus.RUNNING,
            log_file=log_file,
            is_daemon=daemon_flag,
            terminal_id=term_id,
        )
        self._tasks[task_id] = task_record
        self._processes[task_id] = process

        # Start background stream pump
        stream_job = asyncio.create_task(
            self._stream_output(process, log_file, task_id)
        )
        self._background_jobs[task_id] = stream_job

        timeout_seconds = max(0.0, wait_ms / 1000.0)

        # Adaptive sync vs async check
        if timeout_seconds > 0:
            try:
                await asyncio.wait_for(process.wait(), timeout=timeout_seconds)
                # Completed synchronously! Wait for streams to finish flushing
                await stream_job
                output_content = (
                    log_file.read_text(encoding="utf-8", errors="replace")
                    if log_file.exists()
                    else ""
                )
                return {
                    "is_async": False,
                    "task_id": task_id,
                    "output": output_content,
                    "exit_code": process.returncode,
                    "status": task_record.status.value,
                    "log_file": str(log_file),
                    "terminal_id": term_id,
                }
            except asyncio.TimeoutError:
                # Timed out -> Keep running in background!
                pass

        # Transitioned to background task
        return {
            "is_async": True,
            "task_id": task_id,
            "status": TaskStatus.RUNNING.value,
            "log_file": str(log_file),
            "terminal_id": term_id,
            "message": (
                f"Command exceeded {wait_ms}ms; transitioned to background task {task_id}."
            ),
        }

    async def _stream_output(
        self,
        process: asyncio.subprocess.Process,
        log_file: Path,
        task_id: str,
    ) -> None:
        """Pumps stdout and stderr to persistent log file and event bus in real time."""
        task_record = self._tasks.get(task_id)

        try:
            with open(log_file, "a", encoding="utf-8") as fp:
                async def pump(
                    reader: Optional[asyncio.StreamReader],
                    stream_type: str,
                ) -> None:
                    if not reader:
                        return
                    while True:
                        try:
                            chunk = await reader.read(4096)
                            if not chunk:
                                break
                            text = chunk.decode("utf-8", errors="replace")
                            fp.write(text)
                            fp.flush()
                            if self.event_bus:
                                await self.event_bus.publish(
                                    TaskOutputEvent(
                                        source_id=task_id,
                                        chunk=text,
                                        stream=stream_type,  # type: ignore[arg-type]
                                    )
                                )
                        except asyncio.CancelledError:
                            break
                        except Exception as ex:
                            logger.debug("Error pumping %s for %s: %s", stream_type, task_id, ex)
                            break

                await asyncio.gather(
                    pump(process.stdout, "stdout"),
                    pump(process.stderr, "stderr"),
                )

            await process.wait()

            if task_record:
                task_record.exit_code = process.returncode
                if task_record.status != TaskStatus.KILLED:
                    new_st = (
                        TaskStatus.DONE if process.returncode == 0 else TaskStatus.FAILED
                    )
                    task_record.status = new_st

                    if self.event_bus:
                        await self.event_bus.publish(
                            TaskStatusChangedEvent(
                                source_id=task_id,
                                old_status=TaskStatus.RUNNING.value,
                                new_status=new_st.value,
                                exit_code=process.returncode,
                                summary=f"Task {task_id} completed with code {process.returncode}",
                            )
                        )
        except Exception as e:
            logger.error("Exception in _stream_output for %s: %s", task_id, e, exc_info=True)

    # ------------------------------------------------------------------------
    # Task Management (manage_task, kill, status, stdin)
    # ------------------------------------------------------------------------

    async def kill_task(self, task_id: str) -> bool:
        """Terminate a background task cleanly via process group termination."""
        task = self._tasks.get(task_id)
        if not task:
            return False
        if task.status in (TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.KILLED):
            return False

        proc = self._processes.get(task_id)
        if not proc:
            task.status = TaskStatus.KILLED
            return True

        task.status = TaskStatus.KILLED

        pgid: Optional[int] = None
        if hasattr(os, "getpgid") and hasattr(os, "killpg"):
            try:
                pgid = os.getpgid(proc.pid)
            except ProcessLookupError:
                pgid = None

        # Send SIGTERM first to process group
        try:
            if pgid is not None:
                os.killpg(pgid, signal.SIGTERM)
            else:
                proc.terminate()
        except ProcessLookupError:
            pass
        except Exception as ex:
            logger.warning("Error terminating process group for %s: %s", task_id, ex)

        # Wait up to 1 second for graceful termination
        try:
            await asyncio.wait_for(proc.wait(), timeout=1.0)
        except asyncio.TimeoutError:
            # Fallback to SIGKILL
            try:
                if pgid is not None:
                    os.killpg(pgid, signal.SIGKILL)
                else:
                    proc.kill()
            except ProcessLookupError:
                pass
            except Exception as ex:
                logger.warning("Error force killing %s: %s", task_id, ex)

            try:
                await asyncio.wait_for(proc.wait(), timeout=0.5)
            except asyncio.TimeoutError:
                pass

        task.exit_code = proc.returncode

        if self.event_bus:
            await self.event_bus.publish(
                TaskStatusChangedEvent(
                    source_id=task_id,
                    old_status=TaskStatus.RUNNING.value,
                    new_status=TaskStatus.KILLED.value,
                    exit_code=proc.returncode,
                    summary=f"Task {task_id} killed by user/system",
                )
            )

        return True

    async def send_input(self, task_id: str, input_text: str) -> bool:
        """Send input text into the running task's standard input."""
        task = self._tasks.get(task_id)
        if not task or task.status != TaskStatus.RUNNING:
            return False

        proc = self._processes.get(task_id)
        if not proc or not proc.stdin or proc.stdin.is_closing():
            return False

        try:
            data = input_text.encode("utf-8")
            proc.stdin.write(data)
            await proc.stdin.drain()
            return True
        except Exception as e:
            logger.warning("Failed to send input to %s: %s", task_id, e)
            return False

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get status dictionary for a specific task."""
        task = self._tasks.get(task_id)
        if not task:
            return None
        return {
            "task_id": task.task_id,
            "status": task.status.value,
            "command": task.command,
            "cwd": task.cwd,
            "log_file": str(task.log_file),
            "exit_code": task.exit_code,
            "created_at": task.created_at.isoformat(),
            "is_daemon": task.is_daemon,
            "terminal_id": task.terminal_id,
        }

    def list_tasks(self) -> List[Dict[str, Any]]:
        """List all background tasks."""
        results: List[Dict[str, Any]] = []
        for tid in list(self._tasks.keys()):
            info = self.get_task_status(tid)
            if info:
                results.append(info)
        return results

    async def manage_task(
        self,
        action: Optional[str] = None,
        task_id: Optional[str] = None,
        input_text: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Perform operations on background tasks or timers ('list', 'status', 'send_input', 'kill')."""
        act = (action or kwargs.get("Action") or "").strip().lower()
        tid = task_id or kwargs.get("TaskId") or kwargs.get("task_id")
        inp = input_text or kwargs.get("Input") or kwargs.get("input_text") or ""

        if act == "list":
            return {"tasks": self.list_tasks()}

        if not tid:
            return {"error": "TaskId is required for this action", "success": False}

        # Check timers/crons first if ID matches timer pattern or present in _timers
        if tid in self._timers:
            if act == "status":
                status = self.get_timer_status(tid)
                return status or {"error": f"Timer {tid} not found"}
            if act == "kill":
                success = await self.cancel_timer(tid)
                return {"success": success, "task_id": tid}
            return {"error": f"Action '{act}' not supported on scheduled timer", "success": False}

        if act == "status":
            info = self.get_task_status(tid)
            if info is None:
                return {"error": f"Task {tid} not found", "success": False}
            return info

        if act == "kill":
            success = await self.kill_task(tid)
            return {"success": success, "task_id": tid}

        if act == "send_input":
            success = await self.send_input(tid, inp)
            return {"success": success, "task_id": tid}

        return {"error": f"Unsupported action: '{act}'", "success": False}

    # ------------------------------------------------------------------------
    # Scheduler: One-shot Timers & Cron Schedules
    # ------------------------------------------------------------------------

    async def schedule_timer(
        self,
        prompt: Optional[str] = None,
        duration_s: Optional[float] = None,
        condition: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Schedule a one-shot timer with optional early cancellation condition."""
        p = prompt or kwargs.get("Prompt") or ""
        dur = (
            duration_s
            if duration_s is not None
            else kwargs.get("DurationSeconds", kwargs.get("duration_seconds", 0.0))
        )
        cond = (
            condition
            or kwargs.get("TimerCondition")
            or kwargs.get("timer_condition")
            or "never"
        ).strip()

        # Validate duplicate active conditional timers
        if cond != "never":
            for active_timer in self._timers.values():
                if active_timer.status == "running" and active_timer.condition != "never":
                    if (
                        cond == "any"
                        or active_timer.condition == "any"
                        or cond == active_timer.condition
                    ):
                        raise ValueError(
                            f"A timer with condition '{active_timer.condition}' is already active "
                            f"({active_timer.timer_id})"
                        )

        timer_id = f"timer-{uuid.uuid4().hex[:8]}"
        timer_entry = ScheduledTimer(
            timer_id=timer_id,
            prompt=p,
            is_cron=False,
            duration_s=dur,
            condition=cond,
            status="running",
        )
        self._timers[timer_id] = timer_entry

        cancel_event = asyncio.Event()

        def on_event(event: RuntimeEvent) -> None:
            if event.source_id == timer_id:
                return
            if cond == "any":
                cancel_event.set()
            elif cond == event.source_id:
                cancel_event.set()

        if cond != "never":
            self.event_bus.subscribe(RuntimeEvent, on_event)

        async def _timer_worker() -> None:
            try:
                if dur > 0:
                    if cond != "never":
                        try:
                            await asyncio.wait_for(cancel_event.wait(), timeout=dur)
                            # Early cancellation occurred!
                            timer_entry.status = "cancelled"
                            logger.info(
                                "Timer %s cancelled early due to condition '%s'",
                                timer_id,
                                cond,
                            )
                            return
                        except asyncio.TimeoutError:
                            # Timed out normally without cancellation -> Fire!
                            pass
                    else:
                        await asyncio.sleep(dur)

                # Fire notification event
                timer_entry.status = "done"
                if self.event_bus:
                    await self.event_bus.publish(
                        TimerFiredEvent(
                            timer_id=timer_id,
                            prompt=p,
                            is_cron=False,
                        )
                    )
            except asyncio.CancelledError:
                timer_entry.status = "killed"
            finally:
                if cond != "never":
                    self.event_bus.unsubscribe(RuntimeEvent, on_event)

        task = asyncio.create_task(_timer_worker())
        self._timer_tasks[timer_id] = task
        return timer_id

    async def schedule_cron(
        self,
        prompt: Optional[str] = None,
        cron_expr: Optional[str] = None,
        max_iterations: Optional[int] = None,
        is_daemon: Optional[bool] = None,
        **kwargs: Any,
    ) -> str:
        """Schedule a recurring cron job with 5-field expression and optional max iterations."""
        p = prompt or kwargs.get("Prompt") or ""
        expr = cron_expr or kwargs.get("CronExpression") or "* * * * *"
        max_iter = (
            max_iterations
            if max_iterations is not None
            else kwargs.get("MaxIterations")
        )

        cron_id = f"cron-{uuid.uuid4().hex[:8]}"
        timer_entry = ScheduledTimer(
            timer_id=cron_id,
            prompt=p,
            is_cron=True,
            cron_expr=expr,
            max_iterations=max_iter,
            status="running",
        )
        self._timers[cron_id] = timer_entry

        async def _cron_worker() -> None:
            iterations = 0
            try:
                while True:
                    if max_iter is not None and iterations >= max_iter:
                        timer_entry.status = "done"
                        break

                    now = datetime.now()
                    next_run = get_next_cron_run(expr, base_time=now)
                    delay = max(0.0, (next_run - datetime.now()).total_seconds())

                    await asyncio.sleep(delay)
                    iterations += 1

                    if self.event_bus:
                        await self.event_bus.publish(
                            TimerFiredEvent(
                                timer_id=cron_id,
                                prompt=p,
                                is_cron=True,
                            )
                        )
            except asyncio.CancelledError:
                timer_entry.status = "killed"
            except Exception as e:
                timer_entry.status = "failed"
                logger.error("Error in cron worker %s: %s", cron_id, e)

        task = asyncio.create_task(_cron_worker())
        self._timer_tasks[cron_id] = task
        return cron_id

    def get_timer_status(self, timer_id: str) -> Optional[Dict[str, Any]]:
        """Get status dictionary for a scheduled timer or cron."""
        timer = self._timers.get(timer_id)
        if not timer:
            return None
        return {
            "task_id": timer.timer_id,
            "timer_id": timer.timer_id,
            "prompt": timer.prompt,
            "is_cron": timer.is_cron,
            "cron_expr": timer.cron_expr,
            "condition": timer.condition,
            "status": timer.status,
            "created_at": timer.created_at.isoformat(),
        }

    async def cancel_timer(self, timer_id: str) -> bool:
        """Cancel a running timer or cron job."""
        timer = self._timers.get(timer_id)
        if not timer:
            return False

        task = self._timer_tasks.get(timer_id)
        if task and not task.done():
            task.cancel()

        timer.status = "killed"
        return True

    # ------------------------------------------------------------------------
    # Cleanup & Shutdown
    # ------------------------------------------------------------------------

    async def shutdown(self) -> None:
        """Cleanly terminate all running processes, streams, and scheduled timers."""
        # 1. Kill running tasks
        for tid, task in list(self._tasks.items()):
            if task.status == TaskStatus.RUNNING:
                await self.kill_task(tid)

        # 2. Cancel stream pump background tasks
        for job in list(self._background_jobs.values()):
            if not job.done():
                job.cancel()

        # 3. Cancel all timer / cron tasks
        for tid, timer in list(self._timers.items()):
            if timer.status == "running":
                await self.cancel_timer(tid)
