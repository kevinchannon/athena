"""Tests for MCP server functionality."""

import pytest

from athena import mcp_server


@pytest.mark.asyncio
async def test_list_tools():
    """Test that list_tools returns the ack_locate and ack_info tools."""
    # Call the handler function directly
    tools = await mcp_server.list_tools()

    assert len(tools) == 2

    # Check ack_locate tool
    locate_tool = tools[0]
    assert locate_tool.name == "ack_locate"
    assert "Python" in locate_tool.description
    assert "entity" in locate_tool.inputSchema["properties"]

    # Check ack_info tool
    info_tool = tools[1]
    assert info_tool.name == "ack_info"
    assert "detailed information" in info_tool.description
    assert "location" in info_tool.inputSchema["properties"]


@pytest.mark.asyncio
async def test_call_tool_unknown():
    """Test that calling an unknown tool raises ValueError."""
    with pytest.raises(ValueError, match="Unknown tool"):
        # Call the handler function directly
        await mcp_server.call_tool("nonexistent_tool", {})
