# Athena Code Knowledge

A semantic code analysis tool designed to help Claude Code navigate repositories efficiently while dramatically reducing token consumption.

## Motivation

Claude Code currently incurs significant token costs during repository navigation. A typical planning phase involves reading 10-20 files to understand codebase architecture, consuming substantially more tokens than the targeted modifications themselves. This linear scaling with codebase size makes work on large repositories inefficient.

Most discovery queries ("What does this file contain?", "Where is function X?") don't require reading entire source files. By building a queryable semantic index, we can answer these questions using structured metadata instead, potentially reducing planning token costs by 15-30x.

## What's the deal with the name?
Athena was an Ancient Greek goddess associated with strategic wisdom, logic, crafts, architecture and discipline. She is a patron of engineers and planners, not dreamers. Seemed appropriate.

One of her symbolic animals was the owl.

## Installation

NOTE: Athena currently only works in a Python codebase. More supported languages coming soon!

Install with pipx:
```bash
pipx install athena-code
```
Requires at least Python 3.12, so if that's not installed you should do that with your system package manager. It doesn't need to be the default Python, you can leave that at whatever you want and point Pipx at Python 3.12 explicitly:
```bash
pipx install --python python3.12 athena-code
```

## Usage
use `athena --help` to see up-to-date information about the available features:

```
╭─ Commands ─────────────────────────────────────────────────────────────────────╮
│ locate          Locate entities (functions, classes, methods, modules,         │
│                 packages) by name.                                             │
│ search          Search entities by docstring content using natural language.   │
│ info            Get detailed information about a code entity or package.       │
│ mcp-server      Start the MCP server for Claude Code integration.              │
│ install-mcp     Install MCP server configuration for Claude Code.              │
│ sync            Update @athena hash tags in docstrings.                        │
│ status          Check docstring hash synchronization status.                   │
│ uninstall-mcp   Remove MCP server configuration from Claude Code.              │
╰────────────────────────────────────────────────────────────────────────────────╯
```

Generally, you will install `athena` and then:
- Run `athena sync` in your codebase. This will add Athena's hashes to all the docstrings (for functions, classes, methods, modules, and packages) and allow `athena` to detect code changes that have invalidated the docstrings.
- After code changes, run `athena status` to see a table of all the entities that have been updated and may have had their docstrings invalidated.
- Update the necessary docstrings and then run `athena sync` again to update all the necessary hashes.

### Supported Entity Types

Athena tracks docstrings for:
- **Functions** — Standalone functions
- **Classes** — Class definitions
- **Methods** — Class methods
- **Modules** — Individual Python files (module-level docstrings)
- **Packages** — Directories with `__init__.py` (package-level docstrings in `__init__.py`)

For modules and packages, Athena uses intelligent hashing:
- **Module hashes** are based on the complete file AST (excluding docstrings), capturing all semantic changes
- **Package hashes** are based on `__init__.py` content plus the manifest of direct children (files and sub-packages)
- This means package hashes change when files are added/removed/renamed, but remain stable when only implementation details change within existing modules

If you want to find an entity in the codebase, then just run `athena locate <entity>` to get details on the file and lines the entity occupies:
```bash
> athena locate get_task
 Kind    Path                    Extent
 method  src/tasktree/parser.py  277-286
```

If you want to search for entities based on what they do (rather than their name), use `athena search` with a natural language query:
```bash
> athena search "parse Python code"
 Kind      Path                              Extent   Summary
 class     src/athena/parsers/python_parser  19-400   Parser for extracting entities from Python files
 function  src/athena/parsers/utils.py      45-67    Parse a Python file and return its AST
```

The search command uses FTS5 full-text search to find the most relevant entities based on their docstrings. Exact phrase matches rank highest, followed by standard FTS5-scored results. You can customize the number of results:
```bash
> athena search --max-results 5 "authentication"
> athena search -k 3 "JWT token"  # Short form
```

Search also supports JSON output for programmatic use:
```bash
> athena search --json "parse Python code"
```

Configuration can be customized via a `.athena` file in your repository root:
```yaml
search:
  max_results: 10  # Default number of results
```

Once you know where a thing is, then you can ask for info about it:
`> athena info src/tasktree/parser.py:get_task`
```json
{
  "method": {
    "name": "Recipe.get_task",
    "path": "src/tasktree/parser.py",
    "extent": {
      "start": 277,
      "end": 286
    },
    "sig": {
      "name": "get_task",
      "args": [
        {
          "name": "self"
        },
        {
          "name": "name",
          "type": "str"
        }
      ],
      "return_type": "Task | None"
    },
    "summary": "Get task by name.\n\n        Args:\n            name: Task name (may be namespaced like 'build.compile')\n\n        Returns:\n            Task if found, None otherwise\n        "
  }
}
```

## Install Claude MCP integrations

Athena includes Model Context Protocol (MCP) integration, exposing code navigation capabilities as first-class tools in Claude Code.

### Benefits

- **Native tool discovery** — Tools appear in Claude Code's capabilities list
- **Structured I/O** — Type-safe parameters and responses

### Available Tools

- **`ack_locate`** — Find entity location (file path + line range)
- **`ack_info`** — Get information about an entity (kind, summary, etc.)
- **`ack_status`** — Check whether all docstrings are up-to-date with the code they describe
- **`ack_search`** – Search for code entities using natural language

### Installation

```bash
athena install-mcp
```

This automatically configures Claude Code by adding the MCP server entry to your config file. You will need to restart Claude Code for changes to take effect.

**Uninstalling:**

If you don't like using your Anthropic tokens more efficiently to generate better code, for some reason, then:
```bash
athena uninstall-mcp
```
to remove the MCP integration

## Usage Workflow

```bash
cd /path/to/repository
athena locate validateSession  # Find the locations of entities in the codebase
```

## Contributing

This is an active development project. Early-stage contributions welcome, particularly:

- Tree-sitter AST extraction improvements
- Language-specific signature formatting
- LLM prompt engineering for summary quality
- Performance benchmarking

## License

MIT - See LICENSE
