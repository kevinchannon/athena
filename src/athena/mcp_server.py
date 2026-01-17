"""MCP server that exposes Athena Code Knowledge tools to Claude Code.

This server wraps the `ack` CLI tool, providing structured access to code
navigation capabilities through the Model Context Protocol.
"""

import json
import subprocess
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent


# Initialize MCP server
app = Server("ack")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Declare available tools for Claude Code."""
    return [
        Tool(
            name="ack_locate",
            description=(
                "Find the location of a Python entity (function, class, or method). "
                "Returns file path and line range. Currently supports Python files only. "
                "Use this to locate code before reading files - knowing the exact line "
                "range allows targeted code extraction with tools like sed."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "description": "Name of the entity to locate (e.g., 'validateSession', 'UserModel')",
                    }
                },
                "required": ["entity"],
            },
        ),
        Tool(
            name="ack_info",
            description=(
                "Get detailed information about a code entity including signature, "
                "parameters, return type, docstring, and dependencies. Supports functions, "
                "classes, methods, modules, and packages. Returns structured JSON with all "
                "available metadata about the entity."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": (
                            "Path to entity in format 'file_path:entity_name' for functions/classes/methods, "
                            "'file_path' for module-level info, or 'directory_path' for package info. "
                            "Examples: 'src/auth.py:validate_token', 'src/auth.py', 'src/models'"
                        ),
                    }
                },
                "required": ["location"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls by routing to appropriate CLI commands."""
    if name == "ack_locate":
        return await _handle_locate(arguments["entity"])
    elif name == "ack_info":
        return await _handle_info(arguments["location"])

    raise ValueError(f"Unknown tool: {name}")


async def _handle_locate(entity: str) -> list[TextContent]:
    """Handle ack_locate tool calls.

    Args:
        entity: Name of the entity to locate

    Returns:
        List containing a single TextContent with JSON results
    """
    try:
        # Call the CLI tool
        result = subprocess.run(
            ["ack", "locate", entity],
            capture_output=True,
            text=True,
            check=True,
        )

        # Parse JSON output from CLI
        locations = json.loads(result.stdout)

        if not locations:
            return [
                TextContent(
                    type="text",
                    text=f"No entities found with name '{entity}'",
                )
            ]

        # Format results for Claude Code
        formatted_results = []
        for loc in locations:
            kind = loc["kind"]
            path = loc["path"]
            start = loc["extent"]["start"]
            end = loc["extent"]["end"]
            formatted_results.append(
                f"{kind} '{entity}' found in {path} (lines {start}-{end})"
            )

        return [
            TextContent(
                type="text",
                text="\n".join(formatted_results),
            )
        ]

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else str(e)
        return [
            TextContent(
                type="text",
                text=f"Error running ack locate: {error_msg}",
            )
        ]
    except json.JSONDecodeError as e:
        return [
            TextContent(
                type="text",
                text=f"Error parsing ack output: {e}",
            )
        ]
    except Exception as e:
        return [
            TextContent(
                type="text",
                text=f"Unexpected error: {e}",
            )
        ]


async def _handle_info(location: str) -> list[TextContent]:
    """Handle ack_info tool calls.

    Args:
        location: Path to entity in format "file_path:entity_name",
                 "file_path" for module-level info,
                 or "directory_path" for package info

    Returns:
        List containing a single TextContent with JSON results
    """
    try:
        # Call the CLI tool
        result = subprocess.run(
            ["ack", "info", location],
            capture_output=True,
            text=True,
            check=True,
        )

        # Parse JSON output from CLI
        entity_info = json.loads(result.stdout)

        # Return formatted JSON
        return [
            TextContent(
                type="text",
                text=json.dumps(entity_info, indent=2),
            )
        ]

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else str(e)
        return [
            TextContent(
                type="text",
                text=f"Error running ack info: {error_msg}",
            )
        ]
    except json.JSONDecodeError as e:
        return [
            TextContent(
                type="text",
                text=f"Error parsing ack output: {e}",
            )
        ]
    except Exception as e:
        return [
            TextContent(
                type="text",
                text=f"Unexpected error: {e}",
            )
        ]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
