"""Backend execution environment protocol and errors.

Decouples file operations and shell process execution from specific tools,
providing boundary checks and environment abstraction.
"""

from __future__ import annotations

from typing import List, Protocol, Tuple, runtime_checkable


class PathTraversalError(PermissionError):
    """Raised when an operation attempts to access files outside the allowed root directory."""


@runtime_checkable
class BackendProtocol(Protocol):
    """Abstract execution backend protocol for tool execution."""

    async def read_file(self, path: str) -> str:
        """Read content from file."""
        ...

    async def write_file(self, path: str, content: str) -> None:
        """Write content to file, creating parent directories if needed."""
        ...

    async def edit_file(self, path: str, old_str: str, new_str: str) -> None:
        """Replace occurrences of old_str with new_str in the target file."""
        ...

    async def list_dir(self, path: str = ".") -> List[str]:
        """List files and directories in path."""
        ...

    async def exec_command(self, cmd: str, timeout: float = 60.0) -> Tuple[int, str, str]:
        """Execute a shell command asynchronously and return (exit_code, stdout, stderr)."""
        ...
