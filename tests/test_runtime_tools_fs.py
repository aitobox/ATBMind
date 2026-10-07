"""
Tests for Antigravity-grade filesystem runtime tools:
- ViewFileTool (view_file)
- ReplaceFileContentTool (replace_file_content)
- WriteToFileTool (write_to_file)
"""

import asyncio
from pathlib import Path
import pytest

from atbmind_core.runtime.tools.fs_tools import (
    ViewFileTool,
    WriteToFileTool,
    ReplaceFileContentTool,
)


# ---------------- 1. ViewFileTool Tests ----------------

def test_view_file_slice_and_numbering(tmp_path: Path):
    f = tmp_path / "sample.txt"
    f.write_text("line1\nline2\nline3\nline4\nline5\n")
    tool = ViewFileTool()
    res = tool.execute(AbsolutePath=str(f), StartLine=2, EndLine=4)
    assert res.success is True
    assert "2: line2" in res.output
    assert "3: line3" in res.output
    assert "4: line4" in res.output
    assert "1: line1" not in res.output
    assert "5: line5" not in res.output


def test_view_file_omitted_ranges(tmp_path: Path):
    f = tmp_path / "sample.txt"
    f.write_text("\n".join(f"line_{i}" for i in range(1, 11)) + "\n")
    tool = ViewFileTool()

    # Omit both: entire file (up to 800 lines)
    res_all = tool.execute(AbsolutePath=str(f))
    assert res_all.success is True
    assert "1: line_1" in res_all.output
    assert "10: line_10" in res_all.output

    # StartLine only: from StartLine to end
    res_start = tool.execute(AbsolutePath=str(f), StartLine=7)
    assert res_start.success is True
    assert "7: line_7" in res_start.output
    assert "10: line_10" in res_start.output
    assert "6: line_6" not in res_start.output

    # EndLine only: from 1 to EndLine
    res_end = tool.execute(AbsolutePath=str(f), EndLine=3)
    assert res_end.success is True
    assert "1: line_1" in res_end.output
    assert "3: line_3" in res_end.output
    assert "4: line_4" not in res_end.output


def test_view_file_line_limit_800(tmp_path: Path):
    f = tmp_path / "large.txt"
    f.write_text("\n".join(f"L_{i}" for i in range(1, 1200)) + "\n")
    tool = ViewFileTool()

    # Omit range: maximum 800 lines shown
    res = tool.execute(AbsolutePath=str(f))
    assert res.success is True
    assert "1: L_1" in res.output
    assert "800: L_800" in res.output
    assert "801: L_801" not in res.output


def test_view_file_byte_truncation_and_offset(tmp_path: Path):
    f = tmp_path / "wide.txt"
    # Create large lines exceeding 45KB (46080 bytes)
    big_line = "A" * 200
    f.write_text("\n".join(big_line for _ in range(300)) + "\n")
    tool = ViewFileTool()

    res = tool.execute(AbsolutePath=str(f), StartLine=1, EndLine=250)
    assert res.success is True
    assert "truncated" in res.output.lower()

    # View next slice with ContentOffset
    res_offset = tool.execute(AbsolutePath=str(f), StartLine=1, EndLine=250, ContentOffset=1000)
    assert res_offset.success is True


def test_view_file_binary_detection(tmp_path: Path):
    # Image extension
    img_file = tmp_path / "test.png"
    img_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00")
    tool = ViewFileTool()

    res = tool.execute(AbsolutePath=str(img_file))
    assert res.success is True
    assert "binary" in res.output.lower()
    assert "png" in res.output.lower() or "image" in res.output.lower()

    # Null-byte binary file without extension
    bin_file = tmp_path / "raw_binary"
    bin_file.write_bytes(b"hello\x00world\x00test\xff\xfe")
    res_bin = tool.execute(AbsolutePath=str(bin_file))
    assert res_bin.success is True
    assert "binary" in res_bin.output.lower()


def test_view_file_invalid_inputs(tmp_path: Path):
    tool = ViewFileTool()

    # Non-existent file
    res_missing = tool.execute(AbsolutePath=str(tmp_path / "non_existent.txt"))
    assert res_missing.success is False
    assert "not found" in res_missing.error.lower()

    # Directory
    res_dir = tool.execute(AbsolutePath=str(tmp_path))
    assert res_dir.success is False
    assert "directory" in res_dir.error.lower()

    # StartLine > EndLine
    f = tmp_path / "test.txt"
    f.write_text("a\nb\nc\n")
    res_bad_range = tool.execute(AbsolutePath=str(f), StartLine=3, EndLine=1)
    assert res_bad_range.success is False
    assert "must be greater" in res_bad_range.error.lower() or "must be less" in res_bad_range.error.lower()


# ---------------- 2. ReplaceFileContentTool Tests ----------------

def test_replace_file_content_exact_match(tmp_path: Path):
    f = tmp_path / "code.py"
    f.write_text("def hello():\n    return 42\n")
    tool = ReplaceFileContentTool()
    res = tool.execute(
        TargetFile=str(f),
        StartLine=1,
        EndLine=2,
        TargetContent="    return 42",
        ReplacementContent="    return 100",
        Instruction="update return value",
        Description="change 42 to 100",
    )
    assert res.success is True
    assert f.read_text() == "def hello():\n    return 100\n"


def test_replace_file_content_error_on_mismatch(tmp_path: Path):
    f = tmp_path / "code.py"
    f.write_text("def hello():\n    return 42\n")
    tool = ReplaceFileContentTool()
    res = tool.execute(
        TargetFile=str(f),
        StartLine=1,
        EndLine=2,
        TargetContent="    return 999",
        ReplacementContent="    return 100",
        Instruction="bad replace",
        Description="test",
    )
    assert res.success is False
    assert "not found" in res.error.lower()


def test_replace_file_content_multiple_occurrences(tmp_path: Path):
    f = tmp_path / "code.py"
    f.write_text("item = 1\nitem = 1\nitem = 1\n")
    tool = ReplaceFileContentTool()

    # AllowMultiple is False -> error
    res_fail = tool.execute(
        TargetFile=str(f),
        StartLine=1,
        EndLine=3,
        TargetContent="item = 1",
        ReplacementContent="item = 2",
        AllowMultiple=False,
        Instruction="replace item",
        Description="replace duplicate items",
    )
    assert res_fail.success is False
    assert "multiple" in res_fail.error.lower() or "3 occurrences" in res_fail.error.lower() or "found" in res_fail.error.lower()

    # AllowMultiple is True -> succeeds
    res_ok = tool.execute(
        TargetFile=str(f),
        StartLine=1,
        EndLine=3,
        TargetContent="item = 1",
        ReplacementContent="item = 2",
        AllowMultiple=True,
        Instruction="replace all items",
        Description="replace duplicate items",
    )
    assert res_ok.success is True
    assert f.read_text() == "item = 2\nitem = 2\nitem = 2\n"


def test_replace_file_content_invalid_range_or_missing_file(tmp_path: Path):
    tool = ReplaceFileContentTool()

    # Missing file
    res_missing = tool.execute(
        TargetFile=str(tmp_path / "missing.py"),
        StartLine=1,
        EndLine=2,
        TargetContent="foo",
        ReplacementContent="bar",
        Instruction="test",
        Description="test",
    )
    assert res_missing.success is False
    assert "not found" in res_missing.error.lower()

    # Out of range lines
    f = tmp_path / "simple.py"
    f.write_text("line 1\n")
    res_range = tool.execute(
        TargetFile=str(f),
        StartLine=1,
        EndLine=10,
        TargetContent="line 1",
        ReplacementContent="line 2",
        Instruction="test",
        Description="test",
    )
    assert res_range.success is False
    assert "range" in res_range.error.lower()


# ---------------- 3. WriteToFileTool Tests ----------------

def test_write_to_file_create_and_recursive_dirs(tmp_path: Path):
    nested_file = tmp_path / "deep" / "nested" / "output.txt"
    tool = WriteToFileTool()

    res = tool.execute(
        TargetFile=str(nested_file),
        CodeContent="Hello, World!\nSecond line",
        Description="Create nested file",
    )
    assert res.success is True
    assert nested_file.exists()
    assert nested_file.read_text() == "Hello, World!\nSecond line"


def test_write_to_file_protects_existing_file(tmp_path: Path):
    f = tmp_path / "existing.txt"
    f.write_text("original content")
    tool = WriteToFileTool()

    # Default Overwrite=False, Append=False -> should fail
    res = tool.execute(
        TargetFile=str(f),
        CodeContent="new content",
        Description="try overwrite without flag",
    )
    assert res.success is False
    assert "already exists" in res.error.lower()
    assert f.read_text() == "original content"


def test_write_to_file_overwrite(tmp_path: Path):
    f = tmp_path / "existing.txt"
    f.write_text("original content")
    tool = WriteToFileTool()

    res = tool.execute(
        TargetFile=str(f),
        CodeContent="overwritten content",
        Overwrite=True,
        Description="overwrite existing",
    )
    assert res.success is True
    assert f.read_text() == "overwritten content"


def test_write_to_file_append(tmp_path: Path):
    f = tmp_path / "existing.txt"
    f.write_text("line 1\n")
    tool = WriteToFileTool()

    res = tool.execute(
        TargetFile=str(f),
        CodeContent="line 2\n",
        Append=True,
        Description="append line",
    )
    assert res.success is True
    assert f.read_text() == "line 1\nline 2\n"


def test_write_to_file_conflict_flags(tmp_path: Path):
    f = tmp_path / "conflict.txt"
    tool = WriteToFileTool()

    res = tool.execute(
        TargetFile=str(f),
        CodeContent="test",
        Overwrite=True,
        Append=True,
        Description="both flags",
    )
    assert res.success is False
    assert "cannot set both" in res.error.lower()


# ---------------- 4. Async Execution Compatibility Tests ----------------

@pytest.mark.asyncio
async def test_fs_tools_async_execution(tmp_path: Path):
    f = tmp_path / "async_test.txt"
    write_tool = WriteToFileTool()
    view_tool = ViewFileTool()
    replace_tool = ReplaceFileContentTool()

    # await execute(...)
    w_res = await write_tool.execute(
        TargetFile=str(f),
        CodeContent="foo = 1\nbar = 2\n",
        Description="async write",
    )
    assert w_res.success is True

    # await execute_async(...)
    v_res = await view_tool.execute_async(AbsolutePath=str(f), StartLine=1, EndLine=2)
    assert v_res.success is True
    assert "1: foo = 1" in v_res.output

    # await replace_tool.execute(...)
    r_res = await replace_tool.execute(
        TargetFile=str(f),
        StartLine=1,
        EndLine=2,
        TargetContent="foo = 1",
        ReplacementContent="foo = 99",
        Instruction="async replace",
        Description="update foo",
    )
    assert r_res.success is True
    assert f.read_text() == "foo = 99\nbar = 2\n"


def test_fs_tools_openai_schema_generation():
    for tool_cls in [ViewFileTool, WriteToFileTool, ReplaceFileContentTool]:
        tool = tool_cls()
        schema = tool.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == tool.name
        assert "parameters" in schema["function"]
        assert "properties" in schema["function"]["parameters"]


def test_view_file_end_line_exceeds_total_lines(tmp_path: Path):
    f = tmp_path / "short.txt"
    f.write_text("line1\nline2\n")
    tool = ViewFileTool()
    # EndLine=10 is greater than total lines (2), should not raise IndexError
    res = tool.execute(AbsolutePath=str(f), StartLine=1, EndLine=10)
    assert res.success is True
    assert "1: line1" in res.output
    assert "2: line2" in res.output
    assert "3: " not in res.output


def test_atomic_write_preserves_permissions(tmp_path: Path):
    import os
    script = tmp_path / "script.sh"
    script.write_text("#!/bin/sh\necho 1\n")
    # Set executable permissions (0o755)
    os.chmod(script, 0o755)
    original_mode = os.stat(script).st_mode & 0o777
    assert original_mode == 0o755

    # Replace content and verify permissions preserved
    replace_tool = ReplaceFileContentTool()
    res = replace_tool.execute(
        TargetFile=str(script),
        StartLine=1,
        EndLine=2,
        TargetContent="echo 1",
        ReplacementContent="echo 2",
        Instruction="update script",
        Description="update script",
    )
    assert res.success is True
    new_mode = os.stat(script).st_mode & 0o777
    assert new_mode == 0o755

    # Overwrite via WriteToFileTool and verify permissions preserved
    write_tool = WriteToFileTool()
    w_res = write_tool.execute(
        TargetFile=str(script),
        CodeContent="#!/bin/sh\necho 3\n",
        Overwrite=True,
        Description="overwrite executable",
    )
    assert w_res.success is True
    assert (os.stat(script).st_mode & 0o777) == 0o755

    # New file created does not have 0o600 restricted permission
    new_file = tmp_path / "new_file.txt"
    w_new = write_tool.execute(
        TargetFile=str(new_file),
        CodeContent="hello world",
        Description="new file",
    )
    assert w_new.success is True
    # Verify standard readable permissions (at least 0o644 / owner write & read)
    mode = os.stat(new_file).st_mode & 0o777
    assert mode != 0o600
    assert mode & 0o400  # readable by user
    assert mode & 0o200  # writable by user


def test_replace_file_content_rejects_binary_file(tmp_path: Path):
    img = tmp_path / "test.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
    tool = ReplaceFileContentTool()
    res = tool.execute(
        TargetFile=str(img),
        StartLine=1,
        EndLine=1,
        TargetContent="PNG",
        ReplacementContent="JPG",
        Instruction="bad replace",
        Description="test",
    )
    assert res.success is False
    assert "binary" in res.error.lower()


