import asyncio
import json as json_module

from dataclasses import asdict
from rich.console import Console
from typing import Optional

import typer

from athena import __version__
from athena.info import get_entity_info
from athena.locate import locate_entity
from athena.models import ClassInfo, FunctionInfo, MethodInfo, ModuleInfo, PackageInfo
from athena.repository import RepositoryNotFoundError, find_repository_root
from athena.search import search_docstrings

app = typer.Typer(
    help="Athena Code Knowledge - semantic code analysis tool",
    no_args_is_help=True,
)

console = Console()

@app.command()
def locate(
    entity_name: str,
    json: bool = typer.Option(False, "--json", "-j", help="Output as JSON instead of table")
):
    """Locate entities (functions, classes, methods) by name.

    Args:
        entity_name: The name of the entity to search for
        json: If True, output JSON format; otherwise output as table (default)
    """
    try:
        entities = locate_entity(entity_name)

        if json:
            # Convert entities to dictionaries and remove the name field (internal only)
            results = []
            for entity in entities:
                entity_dict = asdict(entity)
                del entity_dict["name"]  # Name is only for internal filtering
                results.append(entity_dict)

            # Output as JSON
            typer.echo(json_module.dumps(results, indent=2))
        else:
            # Output as table
            from rich.table import Table

            table = Table(show_header=True, header_style="bold cyan", box=None)
            table.add_column("Kind", style="green")
            table.add_column("Path", style="blue")
            table.add_column("Extent", style="yellow")

            for entity in entities:
                extent_str = f"{entity.extent.start}-{entity.extent.end}"
                table.add_row(entity.kind, entity.path, extent_str)

            console.print(table)

    except RepositoryNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2)


@app.command()
def search(
    query: str,
    json: bool = typer.Option(False, "--json", "-j", help="Output as JSON instead of table"),
    max_results: Optional[int] = typer.Option(None, "--max-results", "-k", help="Maximum number of results to return"),
):
    """Search docstrings using FTS5 full-text search.

    Searches all docstrings in the repository using natural language queries
    with FTS5 full-text search and two-tier ranking (exact phrase matches first,
    then standard FTS5 matches).

    Args:
        query: Natural language search query
        json: If True, output JSON format; otherwise output as table (default)
        max_results: Maximum number of results to return (overrides config default)

    Examples:
        athena search "JWT authentication"
        athena search "parse configuration file" --max-results 5
        athena search "full text search" --json
    """
    try:
        # Load config and override max_results if specified
        from athena.config import load_search_config

        config = load_search_config()
        if max_results is not None:
            # Create new config with overridden max_results
            from athena.config import SearchConfig
            config = SearchConfig(max_results=max_results)

        results = search_docstrings(query, config=config)

        if json:
            # Convert results to dictionaries
            results_dicts = []
            for result in results:
                result_dict = asdict(result)
                results_dicts.append(result_dict)

            # Output as JSON
            typer.echo(json_module.dumps(results_dicts, indent=2))
        else:
            # Output as table
            from rich.table import Table

            if not results:
                typer.echo("No results found")
                return

            table = Table(show_header=True, header_style="bold cyan", box=None)
            table.add_column("Kind", style="green")
            table.add_column("Path", style="blue")
            table.add_column("Extent", style="yellow")
            table.add_column("Summary", style="white")

            for result in results:
                extent_str = f"{result.extent.start}-{result.extent.end}"
                # Truncate summary to first line if multi-line
                summary = result.summary.split('\n')[0] if result.summary else ""
                # Truncate summary if too long (max 80 chars)
                if len(summary) > 80:
                    summary = summary[:77] + "..."
                table.add_row(result.kind, result.path, extent_str, summary)

            console.print(table)

    except RepositoryNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2)


@app.command()
def info(location: str):
    """Get detailed information about a code entity or package.

    Args:
        location: Path to entity in format "file_path:entity_name",
                 "file_path" for module-level info,
                 or "directory_path" for package info

    Examples:
        ack info src/auth/session.py:validateSession
        ack info src/auth/session.py
        ack info src/athena
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
    elif isinstance(entity_info, PackageInfo):
        output = {"package": asdict(entity_info)}
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
    typer.echo(json_module.dumps(output, indent=2))


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
def sync(
    entity: Optional[str] = typer.Argument(None, help="Entity to sync (module, class, function, etc.)"),
    force: bool = typer.Option(False, "--force", "-f", help="Force hash recalculation even if valid"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Apply recursively to sub-entities"),
):
    """Update @athena hash tags in docstrings.

    Updates or inserts @athena hash tags in entity docstrings based on their
    current code structure. Hashes are computed from the AST and embedded
    in docstrings for staleness detection.

    If no entity is specified, syncs the entire project recursively.

    Examples:
        athena sync                                   # Sync entire project
        athena sync src/module.py                     # Sync all entities in module
        athena sync src/module.py:MyClass             # Sync specific class
        athena sync src/module.py:MyClass.method      # Sync specific method
        athena sync src/package --recursive           # Sync package recursively
        athena sync src/module.py:func --force        # Force update even if hash matches
    """
    from athena.sync import sync_entity, sync_recursive

    try:
        repo_root = find_repository_root()
    except RepositoryNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=255)

    # If no entity specified, sync entire project
    if entity is None:
        entity = "."
        recursive = True

    try:
        if recursive:
            # Use recursive sync
            update_count = sync_recursive(entity, force, repo_root)
            if update_count > 0:
                typer.echo(f"Updated {update_count} entities")
            else:
                typer.echo("No updates needed")
        else:
            # Use single entity sync
            updated = sync_entity(entity, force, repo_root)
            if updated:
                typer.echo("Updated 1 entity")
            else:
                typer.echo("No updates needed")

    except NotImplementedError as e:
        typer.echo(f"Error: {e}", err=True)
        typer.echo("\nNote: Module and package-level sync requires --recursive flag")
        raise typer.Exit(code=1)
    except (ValueError, FileNotFoundError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2)


def _render_status_table(out_of_sync):
    """Render entity statuses as a table.

    Args:
        out_of_sync: List of EntityStatus objects to render
    """
    from rich.table import Table

    typer.echo(f"{len(out_of_sync)} entities need updating")
    typer.echo()

    table = Table(show_header=True, header_style="bold cyan", box=None)
    table.add_column("Kind", style="green")
    table.add_column("Path", style="blue")
    table.add_column("Extent", style="yellow")
    table.add_column("Recorded Hash", style="magenta")
    table.add_column("Calc. Hash", style="magenta")

    for status_item in out_of_sync:
        recorded = status_item.recorded_hash or "<NONE>"
        extent_str = f"{status_item.extent.start}-{status_item.extent.end}"
        table.add_row(
            status_item.kind,
            status_item.path,
            extent_str,
            recorded,
            status_item.calculated_hash
        )

    console.print(table)


def _render_status_json(out_of_sync):
    """Render entity statuses as JSON.

    Args:
        out_of_sync: List of EntityStatus objects to render
    """
    results = []
    for status_item in out_of_sync:
        status_dict = asdict(status_item)
        # Convert None to null in JSON (not the string "<NONE>")
        # asdict already does this correctly
        results.append(status_dict)

    typer.echo(json_module.dumps(results, indent=2))


@app.command()
def status(
    entity: Optional[str] = typer.Argument(None, help="Entity to check status for"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Check entity and all sub-entities"),
    json: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Check docstring hash synchronization status.

    Displays which entities have out-of-sync @athena hash tags. An entity is
    out-of-sync if it has no hash tag or if the tag doesn't match the current
    code structure.

    If no entity is specified, checks the entire project.

    Examples:
        athena status src/module.py:MyClass            # Check specific class
        athena status src/module.py:MyClass -r         # Check class and methods
        athena status src/module.py --recursive        # Check all entities in module
    """
    from athena.status import check_status, check_status_recursive, filter_out_of_sync

    try:
        repo_root = find_repository_root()
    except RepositoryNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=255)

    # If no entity specified, check entire project recursively
    if entity is None:
        entity = "."
        recursive = True

    try:
        if recursive:
            statuses = check_status_recursive(entity, repo_root)
        else:
            statuses = check_status(entity, repo_root)
        out_of_sync = filter_out_of_sync(statuses)

        if not out_of_sync:
            if json:
                typer.echo("[]")
            else:
                typer.echo("All entities are in sync")
            return

        if json:
            _render_status_json(out_of_sync)
        else:
            _render_status_table(out_of_sync)

    except NotImplementedError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
    except (ValueError, FileNotFoundError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2)


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