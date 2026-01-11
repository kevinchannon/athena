import asyncio
import json
import sys
from dataclasses import asdict

import typer

from athena.locate import locate_entity
from athena.repository import RepositoryNotFoundError

app = typer.Typer(
    help="Athena Code Knowledge - semantic code analysis tool",
    no_args_is_help=False,
)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context, entity_name: str = typer.Argument(None, help="Entity name to locate")):
    """Athena Code Knowledge - semantic code analysis tool.

    When called without a subcommand, assumes 'locate' command for backward compatibility.
    """
    if ctx.invoked_subcommand is None:
        if entity_name is None:
            # No entity name and no subcommand - show help
            typer.echo(ctx.get_help())
            raise typer.Exit()
        else:
            # Entity name provided without subcommand - run locate
            ctx.invoke(locate, entity_name=entity_name)


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
