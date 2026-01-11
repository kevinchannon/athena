import asyncio
import json
from dataclasses import asdict

import typer

from athena.locate import locate_entity
from athena.repository import RepositoryNotFoundError

app = typer.Typer(help="Athena Code Knowledge - semantic code analysis tool")


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
