"""
Antigravity-Grade Filesystem Atomic Toolset.
Implements ViewFileTool (view_file), ReplaceFileContentTool (replace_file_content),
and WriteToFileTool (write_to_file).
"""

from __future__ import annotations

import mimetypes
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type
from pydantic import BaseModel, ConfigDict, Field, model_validator

from atbmind_core.harness.tools.base import AgentTool, ExecutionMode, ToolResult
from atbmind_core.runtime.event_bus import (
    AsyncEventBus,
    FilesChangedEvent,
    get_global_event_bus,
)

# Maximum limits adhering to Antigravity runtime specification
MAX_VIEW_LINES: int = 800
MAX_VIEW_BYTES: int = 46080  # 45 KB
MAX_BINARY_FILE_SIZE: int = 100 * 1024 * 1024  # 100 MB

BINARY_EXTENSIONS = {
    # Images
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".ico", ".tiff", ".tif", ".heic",
    # Audio
    ".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a", ".wma",
    # Video
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm", ".flv", ".m4v",
    # Documents / Binaries
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
    ".exe", ".bin", ".so", ".dylib", ".dll", ".pyc", ".wasm", ".o", ".a",
}


def _is_binary_file(path: str) -> Tuple[bool, str]:
    """Detect if a file is binary using extension heuristics and null-byte sampling."""
    ext = Path(path).suffix.lower()
    if ext in BINARY_EXTENSIONS:
        guessed_type, _ = mimetypes.guess_type(path)
        return True, guessed_type or f"{ext[1:]} file"

    try:
        with open(path, "rb") as f:
            chunk = f.read(1024)
            if b"\x00" in chunk:
                return True, "binary data"
            try:
                chunk.decode("utf-8")
            except UnicodeDecodeError:
                return True, "non-utf8 binary file"
    except Exception:
        pass
    return False, ""


def _atomic_write(path: str, content: str) -> None:
    """Atomically write text content to the target path via a temporary file, preserving permissions."""
    abs_path = os.path.abspath(path)
    parent_dir = os.path.dirname(abs_path) or "."
    os.makedirs(parent_dir, exist_ok=True)

    if os.path.exists(abs_path):
        target_mode = os.stat(abs_path).st_mode & 0o7777
    else:
        current_umask = os.umask(0)
        os.umask(current_umask)
        target_mode = 0o666 & ~current_umask

    temp_file = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=parent_dir, delete=False, encoding="utf-8") as tf:
            tf.write(content)
            tf.flush()
            os.fsync(tf.fileno())
            temp_file = tf.name
        os.chmod(temp_file, target_mode)
        os.replace(temp_file, abs_path)
    except Exception:
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass
        raise



# ============================================================================
# 1. ViewFileTool (view_file)
# ============================================================================

class ViewFileInput(BaseModel):
    """Schema for view_file parameters."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    AbsolutePath: str = Field(..., description="Path to file to view. Must be an absolute path.")
    StartLine: Optional[int] = Field(None, description="1-indexed starting line number (inclusive)")
    EndLine: Optional[int] = Field(None, description="1-indexed ending line number (inclusive)")
    ContentOffset: Optional[int] = Field(None, description="Optional byte offset into the content")

    @model_validator(mode="before")
    @classmethod
    def _normalize_keys(cls, data: Any) -> Any:
        if isinstance(data, dict):
            mapping = {
                "path": "AbsolutePath",
                "absolute_path": "AbsolutePath",
                "start_line": "StartLine",
                "end_line": "EndLine",
                "content_offset": "ContentOffset",
            }
            d = dict(data)
            for k, v in mapping.items():
                if k in d and v not in d:
                    d[v] = d[k]
            return d
        return data


class ViewFileTool(AgentTool):
    """
    View the contents of a file from the local filesystem.
    Supports 1-indexed line numbers, slicing, truncation (max 800 lines & 45KB),
    and binary file detection.
    """
    name = "view_file"
    description = (
        "View the contents of a file from the local filesystem. Supports text files "
        "and binary files (images, pdf, video, audio). 1-indexed lines, max 800 lines & 45KB."
    )
    parameters_schema = ViewFileInput
    execution_mode = ExecutionMode.PARALLEL

    def execute(
        self,
        args: Optional[Dict[str, Any]] = None,
        context: Optional[Any] = None,
        **kwargs: Any,
    ) -> ToolResult:
        merged = {}
        if isinstance(args, dict):
            merged.update(args)
        merged.update(kwargs)

        try:
            params = ViewFileInput.model_validate(merged)
        except Exception as e:
            return ToolResult(content=f"Error: Invalid arguments for view_file: {e}", is_error=True)

        file_path = os.path.abspath(params.AbsolutePath)
        if not os.path.exists(file_path):
            return ToolResult(content=f"Error: File not found at '{file_path}'", is_error=True)

        if os.path.isdir(file_path):
            return ToolResult(content=f"Error: Path '{file_path}' is a directory, not a file", is_error=True)

        file_size = os.path.getsize(file_path)
        if file_size > MAX_BINARY_FILE_SIZE:
            return ToolResult(
                content=f"Error: File size ({file_size} bytes) exceeds maximum allowable limit of 100MB",
                is_error=True,
            )

        # Check binary file
        is_bin, bin_type = _is_binary_file(file_path)
        if is_bin:
            return ToolResult(
                content=f"[Binary file: {bin_type}, size: {file_size} bytes]",
                is_error=False,
                metadata={"is_binary": True, "size": file_size, "path": file_path},
            )

        # Validate line range constraints
        start_line = params.StartLine
        end_line = params.EndLine

        if start_line is not None and end_line is not None and start_line > end_line:
            return ToolResult(
                content=f"Error: StartLine ({start_line}) must be less than or equal to EndLine ({end_line})",
                is_error=True,
            )

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception as exc:
            return ToolResult(content=f"Error reading file '{file_path}': {exc}", is_error=True)

        total_lines = len(lines)
        if total_lines == 0:
            return ToolResult(content="(empty file)", is_error=False, metadata={"total_lines": 0})

        # Calculate slice boundaries adhering to Antigravity rules:
        # - Omit both: entire file or first 800 lines
        # - StartLine only: from StartLine to next 800 lines or EOF
        # - EndLine only: up to EndLine, preceding at most 800 lines
        # - Both: [StartLine, EndLine] capped at 800 lines
        if start_line is None and end_line is None:
            slice_start = 1
            slice_end = min(total_lines, MAX_VIEW_LINES)
        elif start_line is not None and end_line is None:
            slice_start = max(1, start_line)
            slice_end = min(total_lines, slice_start + MAX_VIEW_LINES - 1)
        elif start_line is None and end_line is not None:
            slice_end = min(total_lines, max(1, end_line))
            slice_start = max(1, slice_end - MAX_VIEW_LINES + 1)
        else:
            slice_start = max(1, start_line)
            slice_end = min(total_lines, end_line, slice_start + MAX_VIEW_LINES - 1)

        if slice_start > total_lines:
            return ToolResult(
                content=f"Error: StartLine ({slice_start}) exceeds total lines ({total_lines})",
                is_error=True,
            )

        # Build 1-indexed line output: "<line_number>: <content>"
        formatted_lines = [
            f"{i}: {lines[i - 1].rstrip('\r\n')}"
            for i in range(slice_start, slice_end + 1)
        ]
        full_text = "\n".join(formatted_lines)

        # Byte-level truncation (46080 bytes) and ContentOffset
        raw_bytes = full_text.encode("utf-8")
        offset = params.ContentOffset or 0
        if offset > 0:
            raw_bytes = raw_bytes[offset:]

        if len(raw_bytes) > MAX_VIEW_BYTES:
            truncated = raw_bytes[:MAX_VIEW_BYTES]
            result_content = truncated.decode("utf-8", errors="replace")
            next_offset = offset + MAX_VIEW_BYTES
            result_content += (
                f"\n\n[Content truncated at byte {next_offset}. "
                f"Use ContentOffset={next_offset} to view remaining content]"
            )
        else:
            result_content = raw_bytes.decode("utf-8", errors="replace")

        return ToolResult(
            content=result_content,
            is_error=False,
            metadata={
                "total_lines": total_lines,
                "start_line": slice_start,
                "end_line": slice_end,
                "content_offset": offset,
            },
        )

    async def execute_async(
        self,
        args: Optional[Dict[str, Any]] = None,
        context: Optional[Any] = None,
        **kwargs: Any,
    ) -> ToolResult:
        return self.execute(args, context, **kwargs)


# ============================================================================
# 2. ReplaceFileContentTool (replace_file_content)
# ============================================================================

class ReplaceFileContentInput(BaseModel):
    """Schema for replace_file_content parameters."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    TargetFile: str = Field(..., description="The target file to modify. Must be an absolute path.")
    StartLine: int = Field(..., description="1-indexed starting line number of the chunk (inclusive)")
    EndLine: int = Field(..., description="1-indexed ending line number of the chunk (inclusive)")
    TargetContent: str = Field(..., description="The exact string to be replaced.")
    ReplacementContent: str = Field(..., description="The content to replace the target content with.")
    Instruction: str = Field("", description="A description of the changes that you are making to the file.")
    Description: str = Field("", description="Brief explanation of what this change did.")
    AllowMultiple: bool = Field(False, description="If true, multiple occurrences will be replaced.")

    @model_validator(mode="before")
    @classmethod
    def _normalize_keys(cls, data: Any) -> Any:
        if isinstance(data, dict):
            mapping = {
                "path": "TargetFile",
                "target_file": "TargetFile",
                "start_line": "StartLine",
                "end_line": "EndLine",
                "target_content": "TargetContent",
                "replacement_content": "ReplacementContent",
                "instruction": "Instruction",
                "description": "Description",
                "allow_multiple": "AllowMultiple",
            }
            d = dict(data)
            for k, v in mapping.items():
                if k in d and v not in d:
                    d[v] = d[k]
            return d
        return data


class ReplaceFileContentTool(AgentTool):
    """
    Replaces a single contiguous block of text (TargetContent) with ReplacementContent
    within the line range [StartLine, EndLine].
    """
    name = "replace_file_content"
    description = (
        "Replaces exact TargetContent with ReplacementContent within the line range [StartLine, EndLine]. "
        "Returns error if not found in range or if multiple occurrences found when AllowMultiple=False."
    )
    parameters_schema = ReplaceFileContentInput
    execution_mode = ExecutionMode.SEQUENTIAL

    def __init__(self, event_bus: Optional[AsyncEventBus] = None) -> None:
        self.event_bus = event_bus

    def _notify_files_changed(self, file_path: str, insertions: int, deletions: int) -> None:
        bus = self.event_bus or get_global_event_bus()
        if bus:
            ev = FilesChangedEvent(
                source_id="replace_file_content",
                files=[{
                    "path": file_path,
                    "status": "modified",
                    "insertions": insertions,
                    "deletions": deletions,
                }],
            )
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

    def execute(
        self,
        args: Optional[Dict[str, Any]] = None,
        context: Optional[Any] = None,
        **kwargs: Any,
    ) -> ToolResult:
        merged = {}
        if isinstance(args, dict):
            merged.update(args)
        merged.update(kwargs)

        try:
            params = ReplaceFileContentInput.model_validate(merged)
        except Exception as e:
            return ToolResult(content=f"Error: Invalid arguments for replace_file_content: {e}", is_error=True)

        file_path = os.path.abspath(params.TargetFile)
        if not os.path.exists(file_path):
            return ToolResult(content=f"Error: TargetFile not found at '{file_path}'", is_error=True)

        if os.path.isdir(file_path):
            return ToolResult(content=f"Error: TargetFile '{file_path}' is a directory, not a file", is_error=True)

        is_bin, bin_type = _is_binary_file(file_path)
        if is_bin:
            return ToolResult(
                content=f"Error: Cannot replace content in binary file '{file_path}' ({bin_type})",
                is_error=True,
            )

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace", newline="") as f:
                lines = f.readlines()
        except Exception as exc:
            return ToolResult(content=f"Error reading TargetFile '{file_path}': {exc}", is_error=True)

        total_lines = len(lines)
        if total_lines == 0:
            return ToolResult(content=f"Error: TargetFile '{file_path}' is empty", is_error=True)

        start = params.StartLine
        end = params.EndLine

        if start < 1 or end < start or end > total_lines:
            return ToolResult(
                content=f"Error: Invalid line range [{start}, {end}]. File has {total_lines} lines.",
                is_error=True,
            )

        # Extract target chunk
        chunk_lines = lines[start - 1 : end]
        chunk_text = "".join(chunk_lines)

        target = params.TargetContent
        replacement = params.ReplacementContent

        count = chunk_text.count(target)
        if count == 0:
            # Handle possible CRLF mismatch
            if "\r\n" in chunk_text and "\r\n" not in target:
                target_crlf = target.replace("\n", "\r\n")
                if target_crlf in chunk_text:
                    target = target_crlf
                    replacement = replacement.replace("\n", "\r\n")
                    count = chunk_text.count(target)

        if count == 0:
            return ToolResult(
                content=f"Error: TargetContent not found in lines {start} to {end} of '{file_path}'",
                is_error=True,
            )

        if count > 1 and not params.AllowMultiple:
            return ToolResult(
                content=(
                    f"Error: Found {count} occurrences of TargetContent in lines {start} to {end} "
                    f"of '{file_path}', but AllowMultiple is False."
                ),
                is_error=True,
            )

        # Perform replacement within chunk
        if params.AllowMultiple:
            new_chunk = chunk_text.replace(target, replacement)
        else:
            new_chunk = chunk_text.replace(target, replacement, 1)

        # Reassemble full file
        before = "".join(lines[: start - 1])
        after = "".join(lines[end :])
        new_content = before + new_chunk + after

        try:
            _atomic_write(file_path, new_content)
        except Exception as exc:
            return ToolResult(content=f"Error writing to '{file_path}': {exc}", is_error=True)

        ins = max(1, len(replacement.splitlines()))
        dels = max(1, len(target.splitlines()))
        self._notify_files_changed(file_path, ins, dels)

        return ToolResult(
            content=f"Successfully replaced {count} occurrence(s) in '{file_path}'",
            is_error=False,
            metadata={"occurrences": count, "path": file_path, "description": params.Description},
        )

    async def execute_async(
        self,
        args: Optional[Dict[str, Any]] = None,
        context: Optional[Any] = None,
        **kwargs: Any,
    ) -> ToolResult:
        res = self.execute(args, context, **kwargs)
        import asyncio
        await asyncio.sleep(0)
        return res


# ============================================================================
# 3. WriteToFileTool (write_to_file)
# ============================================================================

class WriteToFileInput(BaseModel):
    """Schema for write_to_file parameters."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    TargetFile: str = Field(..., description="The target file to create and write code to. Must be an absolute path.")
    CodeContent: str = Field(..., description="The code contents to write to the file.")
    Overwrite: bool = Field(False, description="Set this to true to overwrite an existing file.")
    Append: bool = Field(False, description="Set this to true to append CodeContent to the end of TargetFile.")
    Description: str = Field("", description="Brief explanation of what this change did.")
    ArtifactMetadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata for artifacts.")

    @model_validator(mode="before")
    @classmethod
    def _normalize_keys(cls, data: Any) -> Any:
        if isinstance(data, dict):
            mapping = {
                "path": "TargetFile",
                "target_file": "TargetFile",
                "content": "CodeContent",
                "code_content": "CodeContent",
                "overwrite": "Overwrite",
                "append": "Append",
                "description": "Description",
                "artifact_metadata": "ArtifactMetadata",
            }
            d = dict(data)
            for k, v in mapping.items():
                if k in d and v not in d:
                    d[v] = d[k]
            return d
        return data


class WriteToFileTool(AgentTool):
    """
    Creates new files or overwrites/appends to existing files.
    Recursively creates parent directories if needed. Protects existing files unless Overwrite=True or Append=True.
    """
    name = "write_to_file"
    description = (
        "Create new files or overwrite/append to existing files. "
        "Recursively creates parent directories. Protects existing files unless Overwrite=True or Append=True."
    )
    parameters_schema = WriteToFileInput
    execution_mode = ExecutionMode.SEQUENTIAL

    def __init__(self, event_bus: Optional[AsyncEventBus] = None) -> None:
        self.event_bus = event_bus

    def _notify_files_changed(self, file_path: str, status: str, insertions: int, deletions: int) -> None:
        bus = self.event_bus or get_global_event_bus()
        if bus:
            ev = FilesChangedEvent(
                source_id="write_to_file",
                files=[{
                    "path": file_path,
                    "status": status,
                    "insertions": insertions,
                    "deletions": deletions,
                }],
            )
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

    def execute(
        self,
        args: Optional[Dict[str, Any]] = None,
        context: Optional[Any] = None,
        **kwargs: Any,
    ) -> ToolResult:
        merged = {}
        if isinstance(args, dict):
            merged.update(args)
        merged.update(kwargs)

        try:
            params = WriteToFileInput.model_validate(merged)
        except Exception as e:
            return ToolResult(content=f"Error: Invalid arguments for write_to_file: {e}", is_error=True)

        if params.Overwrite and params.Append:
            return ToolResult(content="Error: Cannot set both Overwrite=True and Append=True", is_error=True)

        file_path = os.path.abspath(params.TargetFile)
        file_exists = os.path.exists(file_path)

        if file_exists and not params.Overwrite and not params.Append:
            return ToolResult(
                content=f"Error: TargetFile '{file_path}' already exists. Use Overwrite=True to overwrite, or Append=True to append.",
                is_error=True,
            )

        old_line_count = 0
        if file_exists and not params.Append:
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    old_line_count = len(f.readlines())
            except Exception:
                old_line_count = 0

        try:
            parent_dir = os.path.dirname(file_path) or "."
            os.makedirs(parent_dir, exist_ok=True)

            if file_exists and params.Append:
                with open(file_path, "a", encoding="utf-8") as f:
                    f.write(params.CodeContent)
                msg = f"Successfully appended {len(params.CodeContent)} characters to '{file_path}'"
                self._notify_files_changed(
                    file_path=file_path,
                    status="modified",
                    insertions=max(1, len(params.CodeContent.splitlines())),
                    deletions=0,
                )
            else:
                _atomic_write(file_path, params.CodeContent)
                msg = f"Successfully wrote {len(params.CodeContent)} characters to '{file_path}'"
                self._notify_files_changed(
                    file_path=file_path,
                    status="modified" if file_exists else "added",
                    insertions=max(1, len(params.CodeContent.splitlines())),
                    deletions=old_line_count,
                )

            # If ArtifactMetadata is present, register with ArtifactManager
            if params.ArtifactMetadata:
                try:
                    from atbmind_core.runtime.artifacts import get_global_artifact_manager
                    art_mgr = get_global_artifact_manager()
                    summary_val = str(params.ArtifactMetadata.get("Summary", params.Description or ""))
                    user_facing_val = bool(params.ArtifactMetadata.get("UserFacing", True))
                    req_feedback_val = bool(params.ArtifactMetadata.get("RequestFeedback", False))
                    title_val = str(params.ArtifactMetadata.get("Title", Path(file_path).name))
                    art_mgr.record_artifact(
                        file_path=file_path,
                        content=params.CodeContent,
                        title=title_val,
                        summary=summary_val,
                        user_facing=user_facing_val,
                        request_feedback=req_feedback_val,
                    )
                except Exception as art_err:
                    pass

            return ToolResult(
                content=msg,
                is_error=False,
                metadata={
                    "path": file_path,
                    "description": params.Description,
                    "artifact_metadata": params.ArtifactMetadata,
                },
            )
        except Exception as exc:
            return ToolResult(content=f"Error writing to file '{file_path}': {exc}", is_error=True)

    async def execute_async(
        self,
        args: Optional[Dict[str, Any]] = None,
        context: Optional[Any] = None,
        **kwargs: Any,
    ) -> ToolResult:
        res = self.execute(args, context, **kwargs)
        import asyncio
        await asyncio.sleep(0)
        return res
