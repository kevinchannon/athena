"""Configuration management for athena search functionality."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class SearchConfig:
    """Configuration for FTS5 search.

    Attributes:
        max_results: Maximum number of search results to return.
    """
    max_results: int = 10


def load_search_config(repo_root: Path | None = None) -> SearchConfig:
    """Load search configuration from .athena file in repository root.

    Args:
        repo_root: Path to repository root. If None, uses current directory.

    Returns:
        SearchConfig object with loaded or default values.

    Notes:
        If .athena file doesn't exist or can't be parsed, returns default config.
        Expected YAML structure:

        ```yaml
        search:
          max_results: 10
        ```
    """
    if repo_root is None:
        repo_root = Path.cwd()

    config_path = repo_root / ".athena"

    if not config_path.exists():
        return SearchConfig()

    try:
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            return SearchConfig()

        search_config = data.get("search", {})
        if not isinstance(search_config, dict):
            return SearchConfig()

        return SearchConfig(
            max_results=search_config.get(
                "max_results",
                SearchConfig.max_results
            ),
        )
    except (yaml.YAMLError, OSError, KeyError, TypeError, ValueError):
        # Return default config on any parsing errors
        return SearchConfig()
