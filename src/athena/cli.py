import asyncio
import json

from dataclasses import asdict
from rich.console import Console
from typing import Optional

import typer

from athena import __version__
from athena.info import get_entity_info
from athena.locate import locate_entity
from athena.models import ClassInfo, FunctionInfo, MethodInfo, ModuleInfo
from athena.repository import RepositoryNotFoundError

app = typer.Typer(
    help="Athena Code Knowledge - semantic code analysis tool",
    no_args_is_help=True,
)

console = Console()

@app.command()
def locate(entity_name: str):
    """Locate entities (functions, classes, methods) by name.

    Args:
        entity_name: The name of the entity to search for
    """
    try:
        entities = locate_entity(entity_name)

        # Convert entities to dictionaries and remove the name field (internal only)
        results = []
        for entity in entities:
            entity_dict = asdict(entity)
            del entity_dict["name"]  # Name is only for internal filtering
            results.append(entity_dict)

        # Output as JSON
        typer.echo(json.dumps(results, indent=2))

    except RepositoryNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2)


@app.command()
def info(location: str):
    """Get detailed information about a code entity.

    Args:
        location: Path to entity in format "file_path:entity_name"
                 or just "file_path" for module-level info

    Examples:
        ack info src/auth/session.py:validateSession
        ack info src/auth/session.py
    """
    # Parse location string
    if ":" in location:
        file_path, entity_name = location.rsplit(":", 1)
        # Handle empty entity name after colon
        if not entity_name:
            entity_name = None
    else:
        file_path = location
        entity_name = None

    try:
        # Get entity info
        entity_info = get_entity_info(file_path, entity_name)
    except (FileNotFoundError, ValueError, RepositoryNotFoundError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2)

    # Check if entity was found
    if entity_info is None:
        typer.echo(f"Error: Entity '{entity_name}' not found in {file_path}", err=True)
        raise typer.Exit(code=1)

    # Wrap in discriminated structure
    if isinstance(entity_info, FunctionInfo):
        output = {"function": asdict(entity_info)}
    elif isinstance(entity_info, ClassInfo):
        output = {"class": asdict(entity_info)}
    elif isinstance(entity_info, MethodInfo):
        output = {"method": asdict(entity_info)}
    elif isinstance(entity_info, ModuleInfo):
        output = {"module": asdict(entity_info)}
    else:
        typer.echo(f"Error: Unknown entity type: {type(entity_info)}", err=True)
        raise typer.Exit(code=2)

    # Filter out None values (especially summary field)
    # When summary is None, we want to omit it entirely from JSON
    def filter_none(d):
        if isinstance(d, dict):
            return {k: filter_none(v) for k, v in d.items() if v is not None}
        elif isinstance(d, list):
            return [filter_none(item) for item in d]
        else:
            return d

    output = filter_none(output)

    # Output as JSON
    typer.echo(json.dumps(output, indent=2))


@app.command()
def mcp_server():
    """Start the MCP server for Claude Code integration.

    This command starts the Model Context Protocol server that exposes
    Athena's code navigation tools to Claude Code via structured JSON-RPC.
    """
    from athena.mcp_server import main

    asyncio.run(main())


@app.command()
def install_mcp():
    """Install MCP server configuration for Claude Code.

    This command automatically configures Claude Code to use the Athena
    MCP server by adding the appropriate entry to the Claude config file.
    """
    from athena.mcp_config import install_mcp_config

    success, message = install_mcp_config()

    if success:
        typer.echo(f"✓ {message}")
        typer.echo("\nRestart Claude Code for changes to take effect.")
    else:
        typer.echo(f"✗ {message}", err=True)
        raise typer.Exit(code=1)


@app.command()
def uninstall_mcp():
    """Remove MCP server configuration from Claude Code.

    This command removes the Athena MCP server entry from the Claude
    configuration file.
    """
    from athena.mcp_config import uninstall_mcp_config

    success, message = uninstall_mcp_config()

    if success:
        typer.echo(f"✓ {message}")
        typer.echo("\nRestart Claude Code for changes to take effect.")
    else:
        typer.echo(f"✗ {message}", err=True)
        raise typer.Exit(code=1)


def _version_callback(value: bool):
    """Show version and exit."""
    if value:
        console.print(f"athena version {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit",
    )):
    pass