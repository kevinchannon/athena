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

### Install Claude MCP integrations

Athena includes Model Context Protocol (MCP) integration, exposing code navigation capabilities as first-class tools in Claude Code.

### Benefits

- **Native tool discovery** — Tools appear in Claude Code's capabilities list
- **Structured I/O** — Type-safe parameters and responses

### Available Tools

- **`ack_locate`** — Find Python entity location (file path + line range)

### Installation

```bash
ack install-mcp
```

This automatically configures Claude Code by adding the MCP server entry to your config file. You will need to restart Claude Code for changes to take effect.

**Uninstalling:**

If you don't like using your Anthropic tokens more efficiently to generate better code, for some reason, then:
```bash
ack uninstall-mcp
```
to remove the MCP integration

## Usage Workflow

```bash
cd /path/to/repository
ack locate validateSession  # Find the locations of entities in the codebase
```

## Contributing

This is an active development project. Early-stage contributions welcome, particularly:

- Tree-sitter AST extraction improvements
- Language-specific signature formatting
- LLM prompt engineering for summary quality
- Performance benchmarking

## License

MIT - See LICENSE
