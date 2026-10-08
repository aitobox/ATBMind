# Specification: Issue #71 - Tools BackendProtocol Adoption

## 1. Overview & Context
- **Issue**: [#71](https://github.com/aitobox/ATBMind/issues/71)
- **Parent Epic**: [#69](https://github.com/aitobox/ATBMind/issues/69) (Octop Architecture Adoption Phase 2)
- **Step**: Step 2 of 4
- **Objective**: Refactor ATBMind coding and filesystem tools (`ReadFileTool`, `WriteFileTool`, `EditFileTool`, `BashTool`) to execute via `BackendProtocol` abstraction, supporting dependency injection for sandboxing and in-memory mock testing while preserving backwards compatibility.

## 2. Architecture & Design Details

### 2.1 AgentTool Base (`atbmind_core/harness/tools/base.py`)
- Add optional `backend: Optional[BackendProtocol] = None` parameter to `AgentTool.__init__`.
- Provide property `backend`:
  - Returns injected `_backend` if provided.
  - Defaults to `LocalHostBackend(root_dir=".", allow_escape=True)` for backward-compatible unconstrained execution when no sandbox is specified.
- Provide setter `backend.setter` to dynamically attach or swap backends.

### 2.2 Tool Adaptations (`atbmind_core/harness/tools/coding.py`)
- `BashTool`: Delegated to `self.backend.exec_command(command, timeout=timeout)`.
- `ReadFileTool`: Delegated to `self.backend.read_file(path)` with line range slicing preserved.
- `WriteFileTool`: Delegated to `self.backend.write_file(path, content)`.
- `EditFileTool`: Validates unique match and delegates replacement to `self.backend.edit_file(path, target, replacement)`.

### 2.3 Testing & Mock Isolation
- Add tests in `tests/test_harness_backends.py` demonstrating `MockBackend` execution with tools without disk I/O.
- Ensure all existing tests in `tests/test_harness/test_tools_coding.py` pass without regression.

## 3. Implementation Task List
- [x] Task 1: Module design & contract definitions (`AgentTool.backend` in `tools/base.py`)
- [x] Task 2: Unit tests & TDD test cases (`test_tools_with_backend` in `tests/test_harness_backends.py`)
- [x] Task 3: Refactor tools to use `self.backend` (`ReadFileTool`, `WriteFileTool`, `EditFileTool`, `BashTool` in `tools/coding.py`)
- [x] Task 4: Integration verification & test suite pass (100% pytest pass across all tests)
- [x] Task 5: grill-me audit & stress-testing (mock backend isolation, backward compatibility, timeout)

## 4. Verification Plan
- `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_harness_backends.py tests/test_harness/test_tools_coding.py -v`
- Full regression suite: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/`
