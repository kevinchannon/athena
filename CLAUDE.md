# Athena Project Context

## Overview

Python 3.12+ project using uv for dependency management, src-layout (PEP 420), pytest testing.

**Goal:** Maximize Claude Code efficiency—minimal token usage, maximum code quality.

## Structure

```
athena/
├── src/athena/       # Source (version in __init__.py)
├── tests/            # pytest testss
├── pyproject.toml    # Config/deps
└── CLAUDE.md         # This file
```

## Critical Development Principles

### 0. No backwards compatibility
- Athena is still in early development, **DO NOT** worry about backwards compatibility.
- Athena has no known users in the field, so we do not care what we break in past versions.
- **Clean current code** is MUCH more important that considering breaking changes.

### 1. Small Incremental Commits

- **One logical change per commit** (1 line + tests ideal)
- Break features into smallest viable steps
- **Local work:** Stop after each change for user review/commit
- **GitHub integration:** Auto-commit each increment to feature branch
- Estimate tokens before proceeding: “Next: ~X tokens, remaining: Y”

### 2. Tests Over Scripts

- **Never** write ad hoc test scripts to validate features
- Write proper unit/integration/E2E tests and run them
- Investigate via existing tests when possible
- Plan E2E tests early—validate incrementally

### 3. Efficiency

- Minimize token usage ruthlessly
- Avoid reading entire files unless necessary
- Use targeted queries and focused changes

### 4. Architecture (SOLID + Clean Code)

- Small, named functions over comments
- Abstract logic from types (Liskov substitution)
- Comment WHY, not WHAT (refactor to named functions instead)

## Quick Commands

```bash
tt dev-setup   # Sync deps
tt test        # Run tests
uv run -m athena  # Run app for a quick test
```

Find available commands:
```bash
tt --list
```

## Tool use
You have the following additional tools available:
- **athena** - Use for locating entities such as functions and classes by name.
  - **Prefer this to reading files with grep or find.**
  - Examples:
    - `athena locate some_function` - Find the location(s) of a function
    - `athena info some/path/to/file.py:some_function` - find out what a function does and how to call it

## Adding Dependencies

Edit `pyproject.toml` → `tt dev-setup`

**Dev deps:** Use `[project.optional-dependencies] dev = [...]`