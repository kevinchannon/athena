"""Tests for config module."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from athena.config import SearchConfig, load_search_config


class TestSearchConfig:
    """Tests for SearchConfig dataclass."""

    def test_default_values(self):
        """Test that SearchConfig has correct default values."""
        config = SearchConfig()
        assert config.max_results == 10

    def test_custom_values(self):
        """Test creating SearchConfig with custom values."""
        config = SearchConfig(max_results=20)
        assert config.max_results == 20


class TestLoadSearchConfig:
    """Tests for load_search_config function."""

    def test_no_config_file_returns_defaults(self):
        """Test that missing .athena file returns default config."""
        with TemporaryDirectory() as tmpdir:
            config = load_search_config(Path(tmpdir))
            assert config.max_results == 10

    def test_load_valid_config(self):
        """Test loading valid .athena configuration file."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".athena"
            config_path.write_text("""
search:
  max_results: 20
""")
            config = load_search_config(Path(tmpdir))
            assert config.max_results == 20

    def test_load_partial_config(self):
        """Test loading config with missing max_results uses default."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".athena"
            config_path.write_text("""
search:
  other_field: ignored
""")
            config = load_search_config(Path(tmpdir))
            assert config.max_results == 10  # default

    def test_empty_config_file_returns_defaults(self):
        """Test that empty .athena file returns default config."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".athena"
            config_path.write_text("")
            config = load_search_config(Path(tmpdir))
            assert config.max_results == 10

    def test_missing_search_section_returns_defaults(self):
        """Test that .athena file without search section returns defaults."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".athena"
            config_path.write_text("""
other_section:
  some_key: some_value
""")
            config = load_search_config(Path(tmpdir))
            assert config.max_results == 10

    def test_invalid_yaml_returns_defaults(self):
        """Test that invalid YAML returns default config."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".athena"
            config_path.write_text("invalid: yaml: content: [")
            config = load_search_config(Path(tmpdir))
            assert config.max_results == 10

    def test_wrong_type_search_section_returns_defaults(self):
        """Test that non-dict search section returns defaults."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".athena"
            config_path.write_text("search: not_a_dict")
            config = load_search_config(Path(tmpdir))
            assert config.max_results == 10

    def test_wrong_type_root_returns_defaults(self):
        """Test that non-dict root returns defaults."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".athena"
            config_path.write_text("- list\n- not\n- dict")
            config = load_search_config(Path(tmpdir))
            assert config.max_results == 10

    def test_none_repo_root_uses_cwd(self):
        """Test that None repo_root uses current working directory."""
        # This test just verifies the function doesn't crash with None
        config = load_search_config(None)
        assert isinstance(config, SearchConfig)

    def test_unreadable_file_returns_defaults(self):
        """Test that file read errors return default config."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".athena"
            config_path.write_text("search:\n  max_results: 20")
            # Make file unreadable (on Unix-like systems)
            try:
                config_path.chmod(0o000)
                config = load_search_config(Path(tmpdir))
                assert config.max_results == 10
            finally:
                # Restore permissions for cleanup
                config_path.chmod(0o644)

    def test_config_with_extra_fields(self):
        """Test that extra fields in config are ignored."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".athena"
            config_path.write_text("""
search:
  extra_field: ignored
  max_results: 20
""")
            config = load_search_config(Path(tmpdir))
            assert config.max_results == 20
            assert not hasattr(config, 'extra_field')
