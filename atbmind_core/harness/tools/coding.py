"""
ATBMind Standard Coding and System Tools
Implements bash, read_file, write_file, edit_file, grep, and find_files.
"""

from __future__ import annotations

import asyncio
import fnmatch
import os
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from atbmind_core.harness.tools.base import AgentTool, ExecutionMode, ToolResult

# ----------------- 1. Bash Tool -----------------

class BashInput(BaseModel):
    command: str = Field(..., description="The shell command to execute")
    timeout_seconds: float = Field(60.0, description="Execution timeout in seconds")

class BashTool(AgentTool):
    name = "bash"
    description = "Execute a shell command with timeout and return output (stdout/stderr)."
    parameters_schema = BashInput
    execution_mode = ExecutionMode.SEQUENTIAL

    async def execute(self, args: Dict[str, Any], context: Optional[Any] = None) -> ToolResult:
        command = args.get("command", "").strip()
        timeout = float(args.get("timeout_seconds", 60.0))

        if not command:
            return ToolResult(content="Error: Empty command provided", is_error=True)

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_data, stderr_data = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            stdout_str = stdout_data.decode("utf-8", errors="replace")
            stderr_str = stderr_data.decode("utf-8", errors="replace")

            output_lines = []
            if stdout_str:
                output_lines.append(stdout_str)
            if stderr_str:
                output_lines.append(f"[stderr]\n{stderr_str}")

            output = "\n".join(output_lines).strip()
            if proc.returncode != 0:
                return ToolResult(
                    content=f"Command failed with exit code {proc.returncode}:\n{output}",
                    is_error=True,
                    metadata={"returncode": proc.returncode},
                )
            return ToolResult(content=output or "(no output)", is_error=False, metadata={"returncode": 0})

        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            return ToolResult(
                content=f"Error: Command timed out after {timeout} seconds",
                is_error=True,
            )
        except Exception as exc:
            return ToolResult(content=f"Error executing command: {exc}", is_error=True)

# ----------------- 2. Read File Tool -----------------

class ReadFileInput(BaseModel):
    path: str = Field(..., description="Path to the file to read")
    start_line: Optional[int] = Field(None, description="1-indexed starting line number")
    end_line: Optional[int] = Field(None, description="1-indexed ending line number (inclusive)")

class ReadFileTool(AgentTool):
    name = "read_file"
    description = "Read file content from local filesystem, with optional line range."
    parameters_schema = ReadFileInput
    execution_mode = ExecutionMode.PARALLEL

    async def execute(self, args: Dict[str, Any], context: Optional[Any] = None) -> ToolResult:
        path = args.get("path", "")
        start_line = args.get("start_line")
        end_line = args.get("end_line")

        if not os.path.exists(path):
            return ToolResult(content=f"Error: File not found at '{path}'", is_error=True)

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total_lines = len(lines)
            s_idx = max(0, (start_line - 1)) if start_line is not None else 0
            e_idx = min(total_lines, end_line) if end_line is not None else total_lines

            selected_lines = lines[s_idx:e_idx]
            content = "".join(selected_lines)
            return ToolResult(content=content, is_error=False, metadata={"total_lines": total_lines})
        except Exception as exc:
            return ToolResult(content=f"Error reading file '{path}': {exc}", is_error=True)

# ----------------- 3. Write File Tool -----------------

class WriteFileInput(BaseModel):
    path: str = Field(..., description="Target file path to write to")
    content: str = Field(..., description="File content to write")
    overwrite: bool = Field(True, description="Whether to overwrite if file exists")

class WriteFileTool(AgentTool):
    name = "write_file"
    description = "Create or overwrite a file with given content."
    parameters_schema = WriteFileInput
    execution_mode = ExecutionMode.SEQUENTIAL

    async def execute(self, args: Dict[str, Any], context: Optional[Any] = None) -> ToolResult:
        path = args.get("path", "")
        content = args.get("content", "")
        overwrite = args.get("overwrite", True)

        if os.path.exists(path) and not overwrite:
            return ToolResult(content=f"Error: File already exists at '{path}' and overwrite is False", is_error=True)

        try:
            parent_dir = os.path.dirname(path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return ToolResult(content=f"Successfully wrote {len(content)} characters to '{path}'", is_error=False)
        except Exception as exc:
            return ToolResult(content=f"Error writing file '{path}': {exc}", is_error=True)

# ----------------- 4. Edit File Tool -----------------

class EditFileInput(BaseModel):
    path: str = Field(..., description="Path to the file to edit")
    target_content: str = Field(..., description="Exact string block to be replaced (must match uniquely)")
    replacement_content: str = Field(..., description="Replacement text")

class EditFileTool(AgentTool):
    name = "edit_file"
    description = "Perform exact string replacement in a file. target_content must match uniquely."
    parameters_schema = EditFileInput
    execution_mode = ExecutionMode.SEQUENTIAL

    async def execute(self, args: Dict[str, Any], context: Optional[Any] = None) -> ToolResult:
        path = args.get("path", "")
        target = args.get("target_content", "")
        replacement = args.get("replacement_content", "")

        if not os.path.exists(path):
            return ToolResult(content=f"Error: File not found at '{path}'", is_error=True)

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            count = content.count(target)
            if count == 0:
                return ToolResult(content=f"Error: target_content not found in '{path}'", is_error=True)
            if count > 1:
                return ToolResult(
                    content=f"Error: target_content found {count} times in '{path}'. It must match uniquely.",
                    is_error=True,
                )

            new_content = content.replace(target, replacement, 1)
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return ToolResult(content=f"Successfully replaced 1 occurrence in '{path}'", is_error=False)
        except Exception as exc:
            return ToolResult(content=f"Error editing file '{path}': {exc}", is_error=True)

# ----------------- 5. Grep Tool -----------------

class GrepInput(BaseModel):
    pattern: str = Field(..., description="Regex pattern to search for")
    path: Optional[str] = Field(".", description="Root directory to search")
    max_results: int = Field(50, description="Max matches to return")

class GrepTool(AgentTool):
    name = "grep"
    description = "Search for a regex pattern in files under a directory."
    parameters_schema = GrepInput
    execution_mode = ExecutionMode.PARALLEL

    async def execute(self, args: Dict[str, Any], context: Optional[Any] = None) -> ToolResult:
        pattern = args.get("pattern", "")
        root_path = args.get("path", ".")
        max_results = int(args.get("max_results", 50))

        try:
            regex = re.compile(pattern)
        except re.error as e:
            return ToolResult(content=f"Error: Invalid regex pattern: {e}", is_error=True)

        matches: List[str] = []
        for root, _, files in os.walk(root_path):
            if "/." in root or "\\." in root:
                continue
            for file in files:
                fpath = os.path.join(root, file)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        for lineno, line in enumerate(f, start=1):
                            if regex.search(line):
                                matches.append(f"{fpath}:{lineno}: {line.strip()}")
                                if len(matches) >= max_results:
                                    break
                except (PermissionError, IsADirectoryError):
                    continue
                if len(matches) >= max_results:
                    break
            if len(matches) >= max_results:
                break

        if not matches:
            return ToolResult(content=f"No matches found for pattern '{pattern}'", is_error=False)

        res_str = "\n".join(matches)
        if len(matches) >= max_results:
            res_str += f"\n... (limited to {max_results} results)"
        return ToolResult(content=res_str, is_error=False, metadata={"count": len(matches)})

# ----------------- 6. Find Files Tool -----------------

class FindFilesInput(BaseModel):
    pattern: str = Field("*", description="Glob pattern to match file names (e.g. '*.py')")
    path: Optional[str] = Field(".", description="Root directory to search")
    max_results: int = Field(100, description="Maximum number of files to return")

class FindFilesTool(AgentTool):
    name = "find_files"
    description = "Find files by glob pattern under a directory."
    parameters_schema = FindFilesInput
    execution_mode = ExecutionMode.PARALLEL

    async def execute(self, args: Dict[str, Any], context: Optional[Any] = None) -> ToolResult:
        pattern = args.get("pattern", "*")
        root_path = args.get("path", ".")
        max_results = int(args.get("max_results", 100))

        matched_files: List[str] = []
        for root, _, files in os.walk(root_path):
            if "/." in root or "\\." in root:
                continue
            for file in files:
                if fnmatch.fnmatch(file, pattern):
                    matched_files.append(os.path.join(root, file))
                    if len(matched_files) >= max_results:
                        break
            if len(matched_files) >= max_results:
                break

        if not matched_files:
            return ToolResult(content=f"No files matching pattern '{pattern}' in '{root_path}'", is_error=False)

        res_str = "\n".join(matched_files)
        if len(matched_files) >= max_results:
            res_str += f"\n... (limited to {max_results} results)"
        return ToolResult(content=res_str, is_error=False, metadata={"count": len(matched_files)})
