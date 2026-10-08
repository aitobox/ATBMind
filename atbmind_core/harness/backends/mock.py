"""In-memory mock execution backend for testing tools without disk access."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple


class MockBackend:
    """Mock execution backend operating completely in-memory."""

    def __init__(
        self,
        files: Optional[Dict[str, str]] = None,
        command_responses: Optional[Dict[str, Tuple[int, str, str]]] = None,
    ) -> None:
        self.files: Dict[str, str] = {self._norm(k): v for k, v in (files or {}).items()}
        self.command_responses: Dict[str, Tuple[int, str, str]] = command_responses or {}
        self.executed_commands: List[str] = []

    def _norm(self, path: str) -> str:
        """Normalize relative path representation."""
        p = path.replace("\\", "/").strip()
        while p.startswith("./"):
            p = p[2:]
        return p.strip("/")

    async def read_file(self, path: str) -> str:
        """Read content from in-memory file dict."""
        norm_p = self._norm(path)
        if norm_p not in self.files:
            raise FileNotFoundError(f"File not found: '{path}'")
        return self.files[norm_p]

    async def write_file(self, path: str, content: str) -> None:
        """Write content into in-memory file dict."""
        norm_p = self._norm(path)
        self.files[norm_p] = content

    async def edit_file(self, path: str, old_str: str, new_str: str) -> None:
        """Replace occurrences of old_str with new_str in in-memory file dict."""
        norm_p = self._norm(path)
        if norm_p not in self.files:
            raise FileNotFoundError(f"File not found: '{path}'")
        content = self.files[norm_p]
        if old_str not in content:
            raise ValueError(f"Target content '{old_str}' not found in '{path}'")
        self.files[norm_p] = content.replace(old_str, new_str, 1)

    async def list_dir(self, path: str = ".") -> List[str]:
        """List immediate child files and directory names in path."""
        norm_prefix = self._norm(path)
        entries = set()
        for f in self.files:
            if not norm_prefix or norm_prefix == ".":
                parts = f.split("/")
                if parts and parts[0]:
                    entries.add(parts[0])
            elif f.startswith(norm_prefix + "/"):
                sub = f[len(norm_prefix) + 1 :]
                parts = sub.split("/")
                if parts and parts[0]:
                    entries.add(parts[0])
        return sorted(list(entries))

    async def exec_command(self, cmd: str, timeout: float = 60.0) -> Tuple[int, str, str]:
        """Record command and return preconfigured mock tuple or default (0, '', '')."""
        self.executed_commands.append(cmd)
        return self.command_responses.get(cmd, (0, "", ""))
