"""Localhost execution backend with boundary traversal protection."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List, Tuple, Union

from atbmind_core.harness.backends.protocol import PathTraversalError


class LocalHostBackend:
    """LocalHost execution backend enforcing directory boundary sandboxing."""

    def __init__(self, root_dir: Union[str, Path] = ".", allow_escape: bool = False) -> None:
        self.root_dir = Path(root_dir).resolve()
        self.allow_escape = allow_escape

    def _resolve_path(self, path: Union[str, Path]) -> Path:
        """Resolve and validate path against root_dir sandbox boundary."""
        target = Path(path)
        if target.is_absolute():
            resolved = target.resolve()
        else:
            resolved = (self.root_dir / target).resolve()

        if not self.allow_escape:
            try:
                resolved.relative_to(self.root_dir)
            except ValueError:
                raise PathTraversalError(
                    f"Access denied: path '{path}' escapes root directory '{self.root_dir}'"
                )

        return resolved

    async def read_file(self, path: str) -> str:
        """Read content from file safely within root_dir."""
        target = self._resolve_path(path)

        def _read() -> str:
            if not target.exists():
                raise FileNotFoundError(f"File not found: '{path}'")
            if target.is_dir():
                raise IsADirectoryError(f"Path is a directory: '{path}'")
            return target.read_text(encoding="utf-8", errors="replace")

        return await asyncio.to_thread(_read)

    async def write_file(self, path: str, content: str) -> None:
        """Write content to file safely, creating parent directories as needed."""
        target = self._resolve_path(path)

        def _write() -> None:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

        await asyncio.to_thread(_write)

    async def edit_file(self, path: str, old_str: str, new_str: str) -> None:
        """Replace occurrences of old_str with new_str safely within root_dir."""
        target = self._resolve_path(path)

        def _edit() -> None:
            if not target.exists():
                raise FileNotFoundError(f"File not found: '{path}'")
            data = target.read_text(encoding="utf-8", errors="replace")
            if old_str not in data:
                raise ValueError(f"Target content '{old_str}' not found in '{path}'")
            new_data = data.replace(old_str, new_str, 1)
            target.write_text(new_data, encoding="utf-8")

        await asyncio.to_thread(_edit)

    async def list_dir(self, path: str = ".") -> List[str]:
        """List files and directories in path safely within root_dir."""
        target = self._resolve_path(path)

        def _list() -> List[str]:
            if not target.exists():
                raise FileNotFoundError(f"Directory not found: '{path}'")
            if not target.is_dir():
                raise NotADirectoryError(f"Path is not a directory: '{path}'")
            return sorted([item.name for item in target.iterdir()])

        return await asyncio.to_thread(_list)

    async def exec_command(self, cmd: str, timeout: float = 60.0) -> Tuple[int, str, str]:
        """Execute a shell command with root_dir working directory and timeout."""
        proc = await asyncio.create_subprocess_shell(
            cmd,
            cwd=str(self.root_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )
            stdout_str = stdout_bytes.decode("utf-8", errors="replace")
            stderr_str = stderr_bytes.decode("utf-8", errors="replace")
            return (proc.returncode if proc.returncode is not None else 0, stdout_str, stderr_str)
        except asyncio.TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except ProcessLookupError:
                pass
            raise TimeoutError(f"Command '{cmd}' timed out after {timeout} seconds")
