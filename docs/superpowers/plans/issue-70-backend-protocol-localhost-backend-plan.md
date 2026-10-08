# Implementation Plan - Issue #70: BackendProtocol & LocalHostBackend

## Overview
Implement the foundational backend execution layer (`BackendProtocol`, `LocalHostBackend`, and `MockBackend`) to decouple tools from direct OS calls and enforce path boundary sandboxing against Path Traversal attacks.

## Proposed Changes

### 1. `atbmind_core/harness/backends/protocol.py`
- Define `PathTraversalError(PermissionError)`
- Define runtime-checkable `BackendProtocol`:
  - `read_file(path: str) -> str`
  - `write_file(path: str, content: str) -> None`
  - `edit_file(path: str, old_str: str, new_str: str) -> None`
  - `list_dir(path: str = ".") -> list[str]`
  - `exec_command(cmd: str, timeout: float = 60.0) -> tuple[int, str, str]`

### 2. `atbmind_core/harness/backends/local.py`
- Implement `LocalHostBackend`:
  - Constructor: `LocalHostBackend(root_dir: str | Path = ".", allow_escape: bool = False)`
  - Safe path resolver `_resolve_path`: canonicalize with `resolve()`, check relative-to boundary, raise `PathTraversalError` on escape.
  - Async file operations with parent directory auto-creation on write.
  - Subprocess command execution with cwd set to root_dir, output capturing, and timeout enforcement with clean process termination on timeout.

### 3. `atbmind_core/harness/backends/mock.py`
- Implement `MockBackend`:
  - In-memory file storage `files: dict[str, str]`
  - Command output map and execution log `executed_commands: list[str]`
  - Adherence to `BackendProtocol`

### 4. `atbmind_core/harness/backends/__init__.py`
- Export `BackendProtocol`, `LocalHostBackend`, `MockBackend`, `PathTraversalError`.

### 5. `tests/test_harness_backends.py`
- Comprehensive test cases:
  - `test_localhost_backend_read_write_file`
  - `test_localhost_backend_edit_file`
  - `test_localhost_backend_list_dir`
  - `test_localhost_backend_exec_command_success`
  - `test_localhost_backend_exec_command_timeout`
  - `test_localhost_backend_path_traversal_prevention`
  - `test_localhost_backend_allow_escape_override`
  - `test_mock_backend_operations`
  - `test_backend_protocol_conformance`

## Verification
- `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_harness_backends.py -v`
- `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/`
