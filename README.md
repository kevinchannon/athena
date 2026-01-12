Work in Progress!

# Athena Code Knowledge (`ack`)

A semantic code analysis tool designed to help Claude Code navigate repositories efficiently while dramatically reducing token consumption.

## Motivation

Claude Code currently incurs significant token costs during repository navigation. A typical planning phase involves reading 10-20 files to understand codebase architecture, consuming substantially more tokens than the targeted modifications themselves. This linear scaling with codebase size makes work on large repositories inefficient.

Most discovery queries ("What does this file contain?", "Where is function X?") don't require reading entire source files. By building a queryable semantic index, we can answer these questions using structured metadata instead, potentially reducing planning token costs by 15-30x.

## What's the deal with the name?
Athena was an Ancient Greek goddess associated with strategic wisdom, logic, crafts, architecture and discipline. She is a patron of engineers and planners, not dreamers. Seemed appropriate.

One of her symbolic animals was the owl.

## Key Design Principles

1. **Cache only what's expensive** — LLM summaries go in persistent storage; signatures and docstrings are extracted on-demand from AST parsing
2. **Always-accurate positions** — Line ranges are computed from AST on every query, never stored, ensuring data never becomes stale
3. **Unified output format** — All queries return `{sig, docs, summary}` structure where available
4. **AST-based change detection** — Formatting and comment changes don't invalidate summaries

## Architecture Overview

The tool comprises three layers:

- **CLI interface** — Simple, composable commands outputting JSON
- **Tree-sitter AST parser** — On-demand extraction of signatures, docstrings, and line ranges
- **Persistent cache** — Stores only expensive LLM-generated summaries and AST hashes

### Supported Languages

- Python
- JavaScript
- TypeScript

All three have mature, production-grade tree-sitter support.

## Output Format

All entity queries return a consistent three-tier information structure:

```json
{
  "path": "src/auth/session.ts",
  "extent": { "start": 88, "end": 105 },
  "sig": "validateSession(token: string): Promise<User>",
  "docs": "Validates JWT token and returns user object.",
  "summary": "Verifies JWT signature and expiry, queries database for session status, returns User object or raises AuthError."
}
```

Information hierarchy for Claude Code:
1. **`summary`** (if present) — LLM-generated semantic description
2. **`docs`** (fallback) — Author-written docstring
3. **`sig`** (fallback) — Structural signature from AST

## Implementation Roadmap

### Stage 1: AST-Only Queries

**Goal:** Deliver immediate utility with zero LLM cost and no persistent storage.

**Features:**
- `ack locate <entity>` — Find entity and return file path + line range
- `ack info <entity>` — Return `{sig, docs, summary}` with `summary: null`
- `ack file-info <path>` — File-level overview with entity list

**Example:**
```bash
$ ack locate validateSession
{"path": "src/auth/session.ts", "extent": { "start": 88, "end": 105 }}

$ ack info validateSession
{
  "path": "src/auth/session.ts",
  "extent": { "start": 88, "end": 105 },
  "sig": "validateSession(token: string): Promise<User>",
  "docs": "Validates JWT token and returns user object.",
  "summary": null
}
```

**Deliverable:** Working CLI tool, ~500 lines of code, immediate value for small repositories.

### Stage 2: Persistent Caching

**Goal:** Scale to large repositories through entity indexing.

**Features:**
- `ack init` — Scan repository, build entity index
- `ack update` — Detect changed files, refresh index
- AST hash-based change detection
- Fast entity lookups without re-parsing

**Example:**
```bash
$ ack init
Scanning repository...
Found 234 files, 1,842 entities
Index created: .ack/index.db

$ ack update
Detected 3 changed files
Updated 12 entity hashes
```

**Deliverable:** Tool that queries 10k-file repositories in <50ms.

**Technical details:** 
- Store only entity metadata (name, file path, AST hash) and LLM summaries
- Signatures, docstrings, and line ranges extracted on-demand (never cached)
- Change detection based on AST structure, not text formatting

### Stage 3: LLM Semantic Summaries

**Goal:** Add rich semantic descriptions for comprehensive code understanding.

**Features:**
- `ack summarise` — Generate LLM summaries for all entities
- `ack summarise <entity>` — Generate summary for specific entity
- Batch processing for LLM efficiency
- Summary invalidation on semantic (not formatting) changes

**Example:**
```bash
$ ack summarise
Processing 1,842 entities in batches of 50...
Generated 1,842 LLM summaries
Total tokens used: 45,000

$ ack info validateSession
{
  "path": "src/auth/session.ts",
  "extent": { "start": 88, "end": 105 },
  "sig": "validateSession(token: string): Promise<User>",
  "docs": "Validates JWT token and returns user object.",
  "summary": "Verifies JWT signature and expiry, queries database for active session status, returns User object or raises AuthError."
}
```

**Deliverable:** Complete semantic navigation capability with 20-50x token reduction for discovery workflows.

**Summary invalidation strategy:**
- Formatting changes (whitespace, comments) → no re-summarisation
- Docstring updates → no re-summarisation (docstrings separate from summaries)
- Signature or control flow changes → summary marked invalid
- User runs `ack update` to detect, `ack summarise` to regenerate

## Token Efficiency Analysis

**Current Claude Code workflow** (without tool):
1. "What files handle authentication?" → scan 10 files (20,000 tokens)
2. "What's in session.ts?" → read full file (2,000 tokens)
3. "Where's validateSession?" → already in context
4. Make modification → include full file context (2,000 tokens)

**Total:** ~24,000 tokens

**With `ack` (Stage 3):**
1. "What files handle authentication?" → `ack file-info` with summaries (300 tokens)
2. "What's in session.ts?" → already have summary
3. "Where's validateSession?" → `ack info` includes rich summary (100 tokens)
4. Extract function → `sed -n '88,105p'` (150 tokens)

**Total:** ~550 tokens  
**Reduction:** 44x

**Amortisation:**
- Stage 1 cost: Zero (no LLM, no storage)
- Stage 2 cost: ~100ms one-time indexing
- Stage 3 cost: 45,000 tokens one-time (example 1,842-entity repo)
- Break-even: After 2 complex queries
- Ongoing cost: Near-zero (summaries rarely invalidate)

## MCP Integration

Athena includes Model Context Protocol (MCP) integration, exposing code navigation capabilities as first-class tools in Claude Code.

### Benefits

- **Native tool discovery** — Tools appear in Claude Code's capabilities list
- **Structured I/O** — Type-safe parameters and responses
- **2-3x higher usage** — Compared to CLI-only approach due to better discoverability

### Available Tools

Currently supported:

- **`ack_locate`** — Find Python entity location (file path + line range)

### Installation

Automatic configuration (recommended):

```bash
ack install-mcp
```

This automatically configures Claude Code by adding the MCP server entry to your config file.

Manual configuration:

Add to your Claude Code config file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Linux:** `~/.config/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "ack": {
      "command": "ack",
      "args": ["mcp-server"]
    }
  }
}
```

Restart Claude Code for changes to take effect.

### Troubleshooting

**Tools not appearing:**
- Verify `ack` is installed and in your PATH: `which ack`
- Check Claude Code logs for MCP server errors
- Ensure config file syntax is valid JSON

**Server not starting:**
- Run `ack mcp-server` manually to check for errors
- Verify MCP dependency is installed: `pip show mcp`

**Uninstalling:**

```bash
ack uninstall-mcp
```

## Future Extensions

Beyond current implementation:

- **Reverse semantic search** — "Where is feature X implemented?" using embedding-based search
- **Hierarchical summary trees** — Navigate codebases through semantic relationships
- **Call graph analysis** — "What calls this function?"
- **Impact analysis** — "What breaks if I change this?"

## Technical Stack

- **Language:** Python 3.10+
- **AST parsing:** tree-sitter with language-specific bindings
- **CLI framework:** Typer
- **MCP integration:** Official MCP Python SDK
- **Caching layer:** TBD (considering SQLite, LMDB)
- **LLM client:** Anthropic API (Claude) — Stage 3 only
- **Distribution:** pipx-installable package

## Installation

```bash
pipx install athenacode
```

## Usage Workflow

```bash
# Stage 1: Works immediately
cd /path/to/repository
ack info validateSession

# Stage 2: Create index for speed
ack init

# Stage 3: Generate LLM summaries (optional, costs tokens)
ack summarise

# Daily usage
ack locate <entity>        # Find entity location
ack info <entity>          # Get complete information
ack file-info <path>       # File overview
ack update                 # After code changes
```

## Design Rationale

### Why not cache signatures and docstrings?

AST parsing is cheap (~5ms per file). Caching this data risks staleness—if line numbers shift due to edits elsewhere in the file, cached positions become incorrect. By parsing on-demand, we guarantee accuracy.

### Why cache LLM summaries?

LLM API calls are expensive (time and tokens). Summaries describe semantic behaviour, which changes far less frequently than formatting or comments. AST-based hashing lets us invalidate summaries only when code semantics actually change.

### Why separate sig/docs/summary fields?

Claude Code needs decision-making flexibility:
- Quick structural understanding → use `sig`
- Author's documented intent → use `docs`  
- Rich semantic context → use `summary`

Not all code is documented; not all projects want LLM costs. The three-tier system provides graceful degradation.

## Contributing

This is an active development project. Early-stage contributions welcome, particularly:

- Tree-sitter AST extraction improvements
- Language-specific signature formatting
- LLM prompt engineering for summary quality
- Performance benchmarking

## License

MIT - See LICENSE

## Development and Installation

```bash
uv sync
```

## Development

Install development dependencies:

```bash
uv sync --extra dev
```

Run tests:

```bash
uv run pytest
```

## Usage

```bash
uv run python -m athena
```

Or use the shorthand:

```bash
uv run -m athena
```
