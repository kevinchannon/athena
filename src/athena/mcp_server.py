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
        Tool(
            name="ack_status",
            description=(
                "Check docstring hash synchronization status for entities. "
                "Shows which entities have out-of-sync @athena hash tags. "
                "An entity is out-of-sync if it has no hash tag or if the tag "
                "doesn't match the current code structure. Returns JSON array of "
                "entities that need updating."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "description": (
                            "Entity to check status for. Use '.' for entire project, "
                            "'file_path' for module, 'file_path:entity_name' for specific entity. "
                            "Examples: '.', 'src/auth.py', 'src/auth.py:MyClass'"
                        ),
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Check entity and all sub-entities recursively (default: false)",
                        "default": False,
                    },
                },
                "required": ["entity"],
            },
        ),
        Tool(
            name="ack_search",
            description=(
                "Search the code for entities by using a natural language description or search term. "
                "Returns JSON array of entities that might match the query"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "A natural language query term describing what you would like to locate. "
                            "Examples: 'Where is JWT authentication handled?', "
                            "'What classes deal with input string validation?', "
                            "'Is there an existing module that does currency conversions?'"
                        ),
                    }
                },
                "required": ["query"],
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
    elif name == "ack_status":
        return await _handle_status(
            arguments["entity"],
            arguments.get("recursive", False)
        )
    elif name == "ack_search":
        return await _handle_search(arguments["query"])

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
            ["athena", "locate", "-j", entity],
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
            ["athena", "info", location],
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


async def _handle_status(entity: str, recursive: bool) -> list[TextContent]:
    """Handle ack_status tool calls.

    Args:
        entity: Entity to check status for
        recursive: Whether to check recursively

    Returns:
        List containing a single TextContent with JSON results
    """
    try:
        # Build command with flags
        cmd = ["athena", "status", "--json"]
        if recursive:
            cmd.append("--recursive")
        cmd.append(entity)

        # Call the CLI tool
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )

        # Parse JSON output from CLI
        status_data = json.loads(result.stdout)

        # Return formatted JSON
        return [
            TextContent(
                type="text",
                text=json.dumps(status_data, indent=2),
            )
        ]

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else str(e)
        return [
            TextContent(
                type="text",
                text=f"Error running ack status: {error_msg}",
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


async def _handle_search(query: str) -> list[TextContent]:
    """Handle ack_search tool calls.

    Args:
        query: A string to try and match entities in the codebase with

    Returns:
        List containing a single TextContent with JSON results
    """
    try:
        # Call the CLI tool
        result = subprocess.run(
            ["athena", "search", "-j", query],
            capture_output=True,
            text=True,
            check=True,
        )

        # Parse JSON output from CLI
        entities = json.loads(result.stdout)

        if not entities:
            return [
                TextContent(
                    type="text",
                    text=f"No entities found with query '{query}'",
                )
            ]

        # Format results for Claude Code
        formatted_results = []
        for entity in entities:
            kind = entity["kind"]
            path = entity["path"]
            start = entity["extent"]["start"]
            end = entity["extent"]["end"]
            summary = entity["summary"]
            formatted_results.append(
                f"{kind} '{entity}' found in {path} (lines {start}-{end})\n   Summary:\n{summary}"
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
                text=f"Error running ack search: {error_msg}",
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
