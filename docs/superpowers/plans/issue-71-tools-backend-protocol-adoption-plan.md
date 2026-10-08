# Implementation Plan - Issue #71: Tools BackendProtocol Adoption

## Overview
Adapt standard coding and filesystem tools (`BashTool`, `ReadFileTool`, `WriteFileTool`, `EditFileTool`) to execute via `BackendProtocol`.

## Proposed Changes

### 1. `atbmind_core/harness/tools/base.py`
- Modify `AgentTool`:
  - `__init__(self, backend: Optional[BackendProtocol] = None) -> None`
  - Property `backend -> BackendProtocol`: returns `self._backend` or defaults to `LocalHostBackend(root_dir=".", allow_escape=True)`
  - Setter `backend(val: Optional[BackendProtocol]) -> None`

### 2. `tests/test_harness_backends.py`
- Add `test_tools_with_mock_backend`:
  - Test `ReadFileTool`, `WriteFileTool`, `EditFileTool`, and `BashTool` instantiated with `MockBackend`
  - Assert that operations succeed in memory and recorded in `MockBackend` without touching physical disk.
- Add `test_tools_with_sandboxed_localhost_backend`:
  - Test sandboxing with `LocalHostBackend(allow_escape=False)` rejecting traversal attempts.

### 3. `atbmind_core/harness/tools/coding.py`
- Refactor `BashTool.execute`: delegate subprocess command execution to `self.backend.exec_command`.
- Refactor `ReadFileTool.execute`: delegate reading to `self.backend.read_file(path)`.
- Refactor `WriteFileTool.execute`: delegate writing to `self.backend.write_file(path, content)`.
- Refactor `EditFileTool.execute`: delegate reading and replacing to `self.backend.read_file` and `self.backend.edit_file`.

### 4. Verification
- `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_harness_backends.py tests/test_harness/test_tools_coding.py -v`
- Full test suite: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/`
