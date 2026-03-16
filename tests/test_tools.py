"""Test tool registry and basic tools."""

import pytest
from tools.registry import execute, list_tools, get_tool_names

# Import tools to register them
import tools.web_search
import tools.web_scrape
import tools.shell
import tools.file_ops
import tools.computer_use


def test_tools_registered():
    """Verify tools are registered."""
    names = get_tool_names()
    assert "web_search" in names
    assert "shell" in names
    assert "file_read" in names
    assert "screenshot" in names


def test_tool_schemas():
    """Verify tool schemas are valid for Claude."""
    schemas = list_tools()
    assert len(schemas) > 0
    for schema in schemas:
        assert "name" in schema
        assert "description" in schema
        assert "input_schema" in schema


@pytest.mark.asyncio
async def test_shell_tool():
    """Test shell command execution."""
    result = await execute("shell", {"command": "echo hello"})
    assert result.success
    assert "hello" in result.output


@pytest.mark.asyncio
async def test_shell_blocked():
    """Test that dangerous commands are blocked."""
    result = await execute("shell", {"command": "rm -rf /"})
    assert "BLOCKED" in result.output


@pytest.mark.asyncio
async def test_file_ops():
    """Test file operations."""
    import tempfile, os

    # Write
    path = os.path.join(tempfile.gettempdir(), "moi_test.txt")
    result = await execute("file_write", {"path": path, "content": "test content"})
    assert result.success

    # Read
    result = await execute("file_read", {"path": path})
    assert result.success
    assert "test content" in result.output

    # Cleanup
    os.unlink(path)


@pytest.mark.asyncio
async def test_unknown_tool():
    """Test calling unknown tool."""
    result = await execute("nonexistent_tool", {})
    assert not result.success
