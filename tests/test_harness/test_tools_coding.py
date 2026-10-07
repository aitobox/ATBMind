import asyncio
import os
import tempfile
import pytest
from atbmind_core.harness.tools.base import ExecutionMode, ToolResult
from atbmind_core.harness.tools.coding import (
    BashTool,
    ReadFileTool,
    WriteFileTool,
    EditFileTool,
    GrepTool,
    FindFilesTool,
)

def test_bash_tool_echo():
    async def _run():
        tool = BashTool()
        assert tool.execution_mode == ExecutionMode.SEQUENTIAL
        res = await tool.execute({"command": "echo 'Hello from bash'"})
        assert not res.is_error
        assert "Hello from bash" in res.content

    asyncio.run(_run())

def test_bash_tool_failure_and_timeout():
    async def _run():
        tool = BashTool()
        res = await tool.execute({"command": "exit 42"})
        assert res.is_error
        assert "exit code 42" in res.content

    asyncio.run(_run())

def test_file_write_and_read():
    async def _run():
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "test.txt")
            write_tool = WriteFileTool()
            read_tool = ReadFileTool()

            # Write
            w_res = await write_tool.execute({"path": fpath, "content": "Line 1\nLine 2\nLine 3\nLine 4"})
            assert not w_res.is_error
            assert os.path.exists(fpath)

            # Read whole
            r_res = await read_tool.execute({"path": fpath})
            assert not r_res.is_error
            assert "Line 1\nLine 2\nLine 3\nLine 4" in r_res.content

            # Read line range (Line 2 to 3)
            r_slice = await read_tool.execute({"path": fpath, "start_line": 2, "end_line": 3})
            assert not r_slice.is_error
            assert "Line 2\nLine 3" in r_slice.content
            assert "Line 1" not in r_slice.content

    asyncio.run(_run())

def test_edit_file_exact_replacement():
    async def _run():
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "edit_test.txt")
            with open(fpath, "w", encoding="utf-8") as f:
                f.write("def foo():\n    return 1\n")

            edit_tool = EditFileTool()

            # Unique match succeeds
            res = await edit_tool.execute({
                "path": fpath,
                "target_content": "return 1",
                "replacement_content": "return 42",
            })
            assert not res.is_error
            with open(fpath, "r", encoding="utf-8") as f:
                assert f.read() == "def foo():\n    return 42\n"

            # Non-existent target fails
            bad_res = await edit_tool.execute({
                "path": fpath,
                "target_content": "not_there",
                "replacement_content": "something",
            })
            assert bad_res.is_error
            assert "not found" in bad_res.content.lower()

    asyncio.run(_run())

def test_grep_and_find_tools():
    async def _run():
        with tempfile.TemporaryDirectory() as tmpdir:
            f1 = os.path.join(tmpdir, "alpha.py")
            f2 = os.path.join(tmpdir, "beta.txt")
            with open(f1, "w") as f:
                f.write("CONSTANT_VAL = 12345\n")
            with open(f2, "w") as f:
                f.write("other info\n")

            grep_tool = GrepTool()
            find_tool = FindFilesTool()

            # Grep pattern
            g_res = await grep_tool.execute({"pattern": "CONSTANT_VAL", "path": tmpdir})
            assert not g_res.is_error
            assert "alpha.py" in g_res.content
            assert "12345" in g_res.content

            # Find files glob
            f_res = await find_tool.execute({"pattern": "*.py", "path": tmpdir})
            assert not f_res.is_error
            assert "alpha.py" in f_res.content
            assert "beta.txt" not in f_res.content

    asyncio.run(_run())
