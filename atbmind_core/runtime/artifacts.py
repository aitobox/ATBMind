"""
Antigravity Artifact System.
Manages persistent user-facing artifacts (reports, diffs, specs, plans) with
versioning, unified diff computation, JSON manifest storage, and event bus notification.
"""

from __future__ import annotations

import difflib
import json
import logging
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, Field

from atbmind_core.runtime.event_bus import (
    AsyncEventBus,
    ArtifactCreatedEvent,
    ArtifactUpdatedEvent,
    get_global_event_bus,
)

logger = logging.getLogger(__name__)


class ArtifactRecord(BaseModel):
    """Data model representing a managed artifact."""

    artifact_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    title: str = ""
    summary: str = ""
    file_path: str = ""
    artifact_type: str = "markdown"  # "markdown", "code", "diff", "plan", "data"
    user_facing: bool = True
    request_feedback: bool = False
    version: int = 1
    content: str = ""
    diff: str = ""
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

    model_config = {"extra": "allow"}


class ArtifactManager:
    """
    Manages persistent session artifacts with automatic diff generation,
    version increments, manifest indexing, and AsyncEventBus notifications.
    """

    def __init__(
        self,
        storage_dir: Optional[Path | str] = None,
        event_bus: Optional[AsyncEventBus] = None,
    ) -> None:
        self.storage_dir = Path(storage_dir or "data/artifacts")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.event_bus = event_bus
        self._artifacts: Dict[str, ArtifactRecord] = {}
        self._path_to_id: Dict[str, str] = {}
        self._load_manifests()

    def _get_manifest_path(self, session_id: str) -> Path:
        s_id = session_id or "default"
        sess_dir = self.storage_dir / s_id
        sess_dir.mkdir(parents=True, exist_ok=True)
        return sess_dir / "manifest.json"

    def _load_manifests(self) -> None:
        if not self.storage_dir.exists():
            return
        for sess_dir in self.storage_dir.iterdir():
            if sess_dir.is_dir():
                mf = sess_dir / "manifest.json"
                if mf.exists():
                    try:
                        data = json.loads(mf.read_text(encoding="utf-8"))
                        for item in data:
                            record = ArtifactRecord.model_validate(item)
                            self._artifacts[record.artifact_id] = record
                            if record.file_path:
                                self._path_to_id[record.file_path] = record.artifact_id
                    except Exception as e:
                        logger.warning("Failed loading artifact manifest %s: %s", mf, e)

    def _save_manifest(self, session_id: str) -> None:
        manifest_path = self._get_manifest_path(session_id)
        records = [
            a.model_dump()
            for a in self._artifacts.values()
            if (a.session_id == session_id or (not a.session_id and session_id == "default"))
        ]
        try:
            manifest_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.warning("Failed saving artifact manifest %s: %s", manifest_path, e)

    def record_artifact(
        self,
        file_path: str,
        content: str,
        session_id: str = "",
        title: str = "",
        summary: str = "",
        user_facing: bool = True,
        request_feedback: bool = False,
        artifact_type: Optional[str] = None,
        artifact_id: Optional[str] = None,
    ) -> ArtifactRecord:
        """
        Creates a new artifact or updates an existing artifact matching file_path or artifact_id.
        Computes unified diff on revisions and emits ArtifactCreatedEvent / ArtifactUpdatedEvent.
        """
        resolved_path = os.path.abspath(file_path) if file_path else ""
        existing_id = artifact_id or self._path_to_id.get(resolved_path)
        is_update = existing_id is not None and existing_id in self._artifacts

        now = time.time()
        effective_title = title or (Path(resolved_path).name if resolved_path else "Artifact")
        ext = Path(resolved_path).suffix.lower() if resolved_path else ""

        if artifact_type is None:
            if ext in (".md", ".markdown"):
                artifact_type = "markdown"
            elif ext in (".py", ".js", ".ts", ".html", ".css", ".rs", ".go", ".cpp", ".json"):
                artifact_type = "code"
            elif ext in (".diff", ".patch"):
                artifact_type = "diff"
            else:
                artifact_type = "data"

        if is_update:
            existing = self._artifacts[existing_id]  # type: ignore[index]
            old_content = existing.content
            new_version = existing.version + 1

            # Compute unified diff
            diff_lines = list(
                difflib.unified_diff(
                    old_content.splitlines(keepends=True),
                    content.splitlines(keepends=True),
                    fromfile=f"v{existing.version}",
                    tofile=f"v{new_version}",
                )
            )
            diff_str = "".join(diff_lines)

            record = ArtifactRecord(
                artifact_id=existing.artifact_id,
                session_id=session_id or existing.session_id,
                title=effective_title,
                summary=summary or existing.summary,
                file_path=resolved_path,
                artifact_type=artifact_type,
                user_facing=user_facing,
                request_feedback=request_feedback,
                version=new_version,
                content=content,
                diff=diff_str,
                created_at=existing.created_at,
                updated_at=now,
            )
        else:
            art_id = artifact_id or str(uuid.uuid4())
            record = ArtifactRecord(
                artifact_id=art_id,
                session_id=session_id,
                title=effective_title,
                summary=summary,
                file_path=resolved_path,
                artifact_type=artifact_type,
                user_facing=user_facing,
                request_feedback=request_feedback,
                version=1,
                content=content,
                diff="",
                created_at=now,
                updated_at=now,
            )

        self._artifacts[record.artifact_id] = record
        if resolved_path:
            self._path_to_id[resolved_path] = record.artifact_id

        # Persist version snapshot
        s_id = session_id or "default"
        sess_dir = self.storage_dir / s_id
        sess_dir.mkdir(parents=True, exist_ok=True)
        version_snap_path = sess_dir / f"{record.artifact_id}_v{record.version}.md"
        try:
            version_snap_path.write_text(content, encoding="utf-8")
        except Exception as e:
            logger.debug("Failed saving artifact snapshot: %s", e)

        self._save_manifest(s_id)

        # Notify EventBus
        bus = self.event_bus or get_global_event_bus()
        if bus:
            event_cls = ArtifactUpdatedEvent if is_update else ArtifactCreatedEvent
            ev = event_cls(source_id=record.artifact_id, artifact=record.model_dump())
            try:
                import asyncio
                loop = asyncio.get_running_loop()
                loop.create_task(bus.publish(ev))
            except RuntimeError:
                try:
                    import asyncio
                    asyncio.run(bus.publish(ev))
                except Exception:
                    pass

        return record

    def get_artifact(self, artifact_id: str) -> Optional[ArtifactRecord]:
        """Retrieves artifact record by artifact_id."""
        return self._artifacts.get(artifact_id)

    def get_by_file_path(self, file_path: str) -> Optional[ArtifactRecord]:
        """Retrieves artifact record by absolute or relative file_path."""
        abs_p = os.path.abspath(file_path)
        art_id = self._path_to_id.get(abs_p)
        return self._artifacts.get(art_id) if art_id else None

    def list_artifacts(self, session_id: Optional[str] = None) -> List[ArtifactRecord]:
        """Lists all artifacts, optionally filtered by session_id."""
        if session_id is None:
            return list(self._artifacts.values())
        return [a for a in self._artifacts.values() if a.session_id == session_id]

    def clear(self) -> None:
        """Clears in-memory artifacts registry."""
        self._artifacts.clear()
        self._path_to_id.clear()


_GLOBAL_ARTIFACT_MANAGER: Optional[ArtifactManager] = None


def get_global_artifact_manager() -> ArtifactManager:
    """Returns the shared global ArtifactManager instance."""
    global _GLOBAL_ARTIFACT_MANAGER
    if _GLOBAL_ARTIFACT_MANAGER is None:
        _GLOBAL_ARTIFACT_MANAGER = ArtifactManager()
    return _GLOBAL_ARTIFACT_MANAGER


def set_global_artifact_manager(manager: Optional[ArtifactManager]) -> None:
    """Sets or resets the shared global ArtifactManager instance."""
    global _GLOBAL_ARTIFACT_MANAGER
    _GLOBAL_ARTIFACT_MANAGER = manager
