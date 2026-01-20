"""Configuration management for athena search functionality."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class SearchConfig:
    """Configuration for BM25 search parameters.

    Attributes:
        term_frequency_saturation: Controls how quickly term frequency
            influence saturates (k1 parameter in BM25). Range: [1.2, 2.0].
        length_normalization: Controls document length normalization
            (b parameter in BM25). Range: [0.5, 0.75].
        max_results: Maximum number of search results to return.
    """
    term_frequency_saturation: float = 1.5
    length_normalization: float = 0.75
    max_results: int = 10

    @property
    def k1(self) -> float:
        """BM25 k1 parameter (term frequency saturation)."""
        return self.term_frequency_saturation

    @property
    def b(self) -> float:
        """BM25 b parameter (length normalization)."""
        return self.length_normalization

    @property
    def k(self) -> int:
        """Number of results to return."""
        return self.max_results


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
          term_frequency_saturation: 1.5
          length_normalization: 0.75
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
            term_frequency_saturation=search_config.get(
                "term_frequency_saturation",
                SearchConfig.term_frequency_saturation
            ),
            length_normalization=search_config.get(
                "length_normalization",
                SearchConfig.length_normalization
            ),
            max_results=search_config.get(
                "max_results",
                SearchConfig.max_results
            ),
        )
    except (yaml.YAMLError, OSError, KeyError, TypeError, ValueError):
        # Return default config on any parsing errors
        return SearchConfig()
