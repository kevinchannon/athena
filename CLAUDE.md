# Athena Project Context

This document provides context and guidelines for working on the Athena project.

## Project Overview

Athena is a Python project using modern Python packaging standards with uv for dependency management.

## Project Structure

```
athena/
├── src/athena/          # Main package source code
│   ├── __init__.py      # Package initialization and version
│   └── __main__.py      # Entry point for `python -m athena`
├── tests/               # Test suite
│   ├── __init__.py
│   └── test_athena.py   # Tests for the package
├── .venv/               # Virtual environment (managed by uv)
├── .gitignore           # Git ignore patterns
├── README.md            # User-facing documentation
├── pyproject.toml       # Project configuration and dependencies
└── CLAUDE.md            # This file - context for Claude Code
```

## IMPORTANT! Development philosophies

### Small, incremental changes
The project team requires that each commit contains a small number of changes. Ideally, just the addition of a new line or statement in the code and an accompanying unit test (or tests) that validate the functionality of that line.

Tickets and features should be iteratively broken down until they can be implemented as a series of small commits.

When prompting the user to move to the next stage, estimate the size of the work and indicate whether you think there is sufficient usage to implement the next stage, or not. ("estimated required tokens: X, remaining usage in this session: Y tokens")

#### Local Claude Code work 
When working locally on a user's machine, Claude Code should NEVER make commits - only stop and ask the user to review and commit, before carrying on with the next incremental change.

#### GitHub Claude Code integration work
When working as a GitHub agent, claude should still BREAK DOWN THE TASK into small, incremental commits, but commit those changes to the feature branch as they are made. GitHub integration Claude Code does not need to ask for permission to commit each change.

### Write tests, not ad hoc test scripts
If you are checking that a feature you are implementing has been implemented correctly, DO NOT write a bespoke test script to check the output of the app with the new functionality. INSTEAD, write a unit/integration/end-to-end test that will confirm you have correctly implemented the feature and RUN JUST THAT TEST. If it passes, you have implemented things correctly; and you can either carry on with additional parts of the feature, or run all the tests to ensure no regressions.

It is still permissible to write and run an ad hoc script to investigate/confirm the current behaviour. Although, it is better to first search for a test that does the thing that you're investigating. If one exists and is passing: then the app does the thing.

### Testas we go!
We do not plan to implement all the code (maybe even with unit tests) and then write a bunch of integration tests. We PLAN END-TO-END incremental changes. This will involve writing high-level test of the functionality as early as possible, to ensure that the new feature is progressing as expected.

### Try to be efficient with token usage
Your sponsor is not made of money! Try to minimise token useage, so that we can maximise the effectiveness of Claude Code on a features per token basis. Obviously, if a thing needs doing and it takes a bunch of tokens, that's just the way it is. Just try to consider/avoid profligacy!

### Architectural philosophies

- Try to follow SOLID principles
- Try to follow the advice in "Clean Code", by Robert Martin.
- Try to keep algorithmic logic abstracted from the TYPES that the logic can be run on. This is a restatement of the Liskov Substitution principle covered in the SOLID principles
- **Small, named functions are preferred over comments**.  If a comment on WHAT the code is doing feels warranted, then refactor that code into a function with an indicative name.  Comment on WHY code is like it is are more permissible.

## Technology Stack

- **Python**: 3.12+
- **Package Manager**: uv
- **Build System**: setuptools
- **Testing**: pytest
- **Project Layout**: src-layout (PEP 420)

## Development Workflow

### Environment Setup

```bash
# Sync dependencies
uv sync

# Install with dev dependencies
uv sync --extra dev
```

### Running the Application

```bash
# Run the main module
uv run python -m athena

# Or shorthand
uv run -m athena
```

### Testing

```bash
# Run all tests (via tasktree)
tt test

# Run with coverage
uv run pytest --cov=athena
```

## Coding Conventions

- Follow PEP 8 style guide
- Use type hints where appropriate
- Keep the src-layout structure
- All source code goes in `src/athena/`
- All tests go in `tests/`

## Adding Dependencies

Add dependencies to `pyproject.toml`:

```toml
dependencies = [
    "package-name>=version",
]
```

For dev dependencies:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "new-dev-tool>=1.0",
]
```

Then sync:

```bash
uv sync
```

## Project Goals

Add your project goals and objectives here as they evolve.

## Notes

- This project uses the src-layout pattern for better isolation and testing
- uv manages the virtual environment in `.venv/`
- Version is defined in both `pyproject.toml` and `src/athena/__init__.py`
