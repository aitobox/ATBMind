"""Unit tests for BackendProtocol, LocalHostBackend, and MockBackend (Issue #70)."""

from __future__ import annotations

import asyncio
from pathlib import Path
import pytest

from atbmind_core.harness.backends.protocol import BackendProtocol, PathTraversalError
from atbmind_core.harness.backends.local import LocalHostBackend
from atbmind_core.harness.backends.mock import MockBackend


@pytest.mark.asyncio
async def test_backend_protocol_runtime_checkable(tmp_path: Path):
    local_backend = LocalHostBackend(root_dir=tmp_path)
    mock_backend = MockBackend()

    assert isinstance(local_backend, BackendProtocol)
    assert isinstance(mock_backend, BackendProtocol)


@pytest.mark.asyncio
async def test_localhost_backend_read_write_file(tmp_path: Path):
    backend = LocalHostBackend(root_dir=tmp_path)

    # 1. Write file
    await backend.write_file("sub/hello.txt", "Hello ATBMind!")
    assert (tmp_path / "sub" / "hello.txt").is_file()

    # 2. Read file
    content = await backend.read_file("sub/hello.txt")
    assert content == "Hello ATBMind!"

    # 3. Read non-existent file raises FileNotFoundError
    with pytest.raises(FileNotFoundError):
        await backend.read_file("sub/non_existent.txt")


@pytest.mark.asyncio
async def test_localhost_backend_edit_file(tmp_path: Path):
    backend = LocalHostBackend(root_dir=tmp_path)
    await backend.write_file("code.py", "def main():\n    return 1\n")

    # 1. Edit existing string
    await backend.edit_file("code.py", "return 1", "return 42")
    content = await backend.read_file("code.py")
    assert "return 42" in content

    # 2. Edit non-matching string raises ValueError
    with pytest.raises(ValueError, match="not found"):
        await backend.edit_file("code.py", "invalid_pattern", "replacement")


@pytest.mark.asyncio
async def test_localhost_backend_list_dir(tmp_path: Path):
    backend = LocalHostBackend(root_dir=tmp_path)
    await backend.write_file("file1.txt", "1")
    await backend.write_file("dir_a/file2.txt", "2")

    root_items = await backend.list_dir(".")
    assert "file1.txt" in root_items
    assert "dir_a" in root_items

    sub_items = await backend.list_dir("dir_a")
    assert sub_items == ["file2.txt"]


@pytest.mark.asyncio
async def test_localhost_backend_exec_command_success(tmp_path: Path):
    backend = LocalHostBackend(root_dir=tmp_path)
    code, stdout, stderr = await backend.exec_command("echo 'hello shell'", timeout=5.0)

    assert code == 0
    assert "hello shell" in stdout
    assert stderr == ""


@pytest.mark.asyncio
async def test_localhost_backend_exec_command_timeout(tmp_path: Path):
    backend = LocalHostBackend(root_dir=tmp_path)

    with pytest.raises(TimeoutError):
        await backend.exec_command("sleep 3", timeout=0.2)


@pytest.mark.asyncio
async def test_localhost_backend_path_traversal_prevention(tmp_path: Path):
    safe_dir = tmp_path / "sandbox"
    safe_dir.mkdir()
    secret_dir = tmp_path / "secret"
    secret_dir.mkdir()
    secret_file = secret_dir / "keys.txt"
    secret_file.write_text("SUPER_SECRET_KEY")

    backend = LocalHostBackend(root_dir=safe_dir, allow_escape=False)

    # 1. Reading file outside root directory must be rejected
    with pytest.raises(PathTraversalError):
        await backend.read_file("../secret/keys.txt")

    # 2. Writing file outside root directory must be rejected
    with pytest.raises(PathTraversalError):
        await backend.write_file("../secret/injected.txt", "pwned")

    # 3. Editing file outside root directory must be rejected
    with pytest.raises(PathTraversalError):
        await backend.edit_file("../secret/keys.txt", "SUPER", "HACKED")

    # 4. Listing directory outside root directory must be rejected
    with pytest.raises(PathTraversalError):
        await backend.list_dir("../secret")

    # 5. Absolute path escaping root directory must also be rejected
    with pytest.raises(PathTraversalError):
        await backend.read_file(str(secret_file))


@pytest.mark.asyncio
async def test_localhost_backend_allow_escape_override(tmp_path: Path):
    safe_dir = tmp_path / "sandbox"
    safe_dir.mkdir()
    other_file = tmp_path / "external.txt"
    other_file.write_text("allowed external content")

    backend = LocalHostBackend(root_dir=safe_dir, allow_escape=True)
    content = await backend.read_file("../external.txt")
    assert content == "allowed external content"


@pytest.mark.asyncio
async def test_mock_backend_operations():
    backend = MockBackend(
        files={"README.md": "# Project Title\nWelcome."},
        command_responses={"git status": (0, "On branch main\nnothing to commit", "")},
    )

    # Read initial mock file
    assert await backend.read_file("README.md") == "# Project Title\nWelcome."

    # Write new mock file
    await backend.write_file("docs/index.md", "Docs content")
    assert await backend.read_file("docs/index.md") == "Docs content"

    # Edit mock file
    await backend.edit_file("README.md", "Welcome", "Hello World")
    assert "Hello World" in await backend.read_file("README.md")

    # List mock files
    files = await backend.list_dir(".")
    assert "README.md" in files
    assert "docs/index.md" in files or "docs" in files

    # Execute mock command
    code, stdout, stderr = await backend.exec_command("git status")
    assert code == 0
    assert "On branch main" in stdout
    assert "git status" in backend.executed_commands

    # Execute unmocked command default
    code2, stdout2, stderr2 = await backend.exec_command("ls")
    assert code2 == 0
    assert "ls" in backend.executed_commands
