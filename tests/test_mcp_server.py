"""Tests for MCP server functionality."""

import pytest

from athena.mcp_server import app


@pytest.mark.asyncio
async def test_list_tools():
    """Test that list_tools returns the ack_locate tool."""
    tools = await app.list_tools()

    assert len(tools) == 1
    tool = tools[0]

    assert tool.name == "ack_locate"
    assert "Python" in tool.description
    assert "entity" in tool.inputSchema["properties"]


@pytest.mark.asyncio
async def test_call_tool_unknown():
    """Test that calling an unknown tool raises ValueError."""
    with pytest.raises(ValueError, match="Unknown tool"):
        await app.call_tool("nonexistent_tool", {})
