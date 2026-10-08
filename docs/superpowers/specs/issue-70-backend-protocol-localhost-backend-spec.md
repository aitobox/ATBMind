# Specification: Issue #70 - BackendProtocol & LocalHostBackend

## 1. Overview & Context
- **Issue**: [#70](https://github.com/aitobox/ATBMind/issues/70)
- **Parent Epic**: [#69](https://github.com/aitobox/ATBMind/issues/69) (Octop Architecture Adoption Phase 2)
- **Step**: Step 1 of 4 (Foundation execution environment abstraction)
- **Objective**: Decouple tool execution from direct local OS / filesystem calls by introducing `BackendProtocol`, secure `LocalHostBackend` with directory boundary enforcement (Path Traversal Guard), and an in-memory `MockBackend` for unit testing.

## 2. Architecture & Contract Design

### 2.1 BackendProtocol (`atbmind_core/harness/backends/protocol.py`)
Runtime checkable Protocol defining asynchronous I/O and process execution contracts:
```python
from typing import Protocol, runtime_checkable

class PathTraversalError(PermissionError):
    """Raised when an operation attempts to access files outside the allowed root directory."""
    pass

@runtime_checkable
class BackendProtocol(Protocol):
    async def read_file(self, path: str) -> str: ...
    async def write_file(self, path: str, content: str) -> None: ...
    async def edit_file(self, path: str, old_str: str, new_str: str) -> None: ...
    async def list_dir(self, path: str = ".") -> list[str]: ...
    async def exec_command(self, cmd: str, timeout: float = 60.0) -> tuple[int, str, str]: ...
```

### 2.2 LocalHostBackend (`atbmind_core/harness/backends/local.py`)
- Initialized with `root_dir: str | Path` and optional `allow_escape: bool = False`.
- Canonicalizes all paths against `root_dir.resolve()`.
- Validates that resolved target paths are strictly within `root_dir` (preventing `../`, symlink attacks, and root escape) unless `allow_escape=True`. Throws `PathTraversalError`.
- `exec_command` runs subprocess with `cwd=self.root_dir` and enforces timeout via `asyncio.wait_for`. On timeout, kills the process and raises `asyncio.TimeoutError`.

### 2.3 MockBackend (`atbmind_core/harness/backends/mock.py`)
- In-memory mock implementing `BackendProtocol`.
- Holds `files: dict[str, str]` and `command_handlers / canned responses`.
- Tracks `executed_commands: list[str]`.
- Enables fast, isolated unit testing for tools without touching physical disk.

## 3. Implementation Task List
- [x] Task 1: Module design & contract definitions (`protocol.py`, `PathTraversalError`)
- [x] Task 2: Unit tests & TDD test cases (`tests/test_harness_backends.py`)
- [x] Task 3: Core logic implementation (`LocalHostBackend`, `MockBackend`, `__init__.py`)
- [x] Task 4: Integration verification & test suite pass (100% pytest pass)
- [x] Task 5: grill-me audit & stress-testing (path traversal, timeout, memory mock)

## 4. Verification Plan
- Unit tests: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_harness_backends.py -v`
- Full regression suite: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/`
