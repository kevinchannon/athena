"""Tests for MCP server functionality."""

import pytest

from athena import mcp_server


@pytest.mark.asyncio
async def test_list_tools():
    """Test that list_tools returns the ack_locate tool."""
    # Call the handler function directly
    tools = await mcp_server.list_tools()

    assert len(tools) == 1
    tool = tools[0]

    assert tool.name == "ack_locate"
    assert "Python" in tool.description
    assert "entity" in tool.inputSchema["properties"]


@pytest.mark.asyncio
async def test_call_tool_unknown():
    """Test that calling an unknown tool raises ValueError."""
    with pytest.raises(ValueError, match="Unknown tool"):
        # Call the handler function directly
        await mcp_server.call_tool("nonexistent_tool", {})
