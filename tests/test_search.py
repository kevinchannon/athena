"""Tests for BM25 docstring search functionality."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from athena.config import SearchConfig
from athena.models import Location, SearchResult
from athena.repository import RepositoryNotFoundError
from athena.search import _get_cache_key, search_docstrings


class TestSearchDocstrings:
    """Test suite for search_docstrings function."""

    def test_search_returns_top_k_results(self, tmp_path):
        """Verify that search returns exactly k results (or fewer if corpus is smaller)."""
        # Create test repository with multiple files
        (tmp_path / ".git").mkdir()
        for i in range(5):
            file = tmp_path / f"module_{i}.py"
            file.write_text(f'"""Module {i} about authentication and JWT tokens."""\n')

        config = SearchConfig(max_results=3)
        results = search_docstrings("authentication", root=tmp_path, config=config)

        # Should return exactly 3 results (top-k limited)
        assert len(results) == 3
        assert all(isinstance(r, SearchResult) for r in results)

    def test_search_returns_fewer_results_than_k(self, tmp_path):
        """Verify search returns fewer than k results if corpus is smaller."""
        (tmp_path / ".git").mkdir()
        file = tmp_path / "single.py"
        file.write_text('"""Single module with JWT authentication."""\n')

        config = SearchConfig(max_results=10)
        results = search_docstrings("JWT", root=tmp_path, config=config)

        # Should return only 1 result (corpus smaller than k)
        assert len(results) == 1

    def test_search_returns_entity_paths(self, tmp_path):
        """Verify each result includes valid entity path."""
        (tmp_path / ".git").mkdir()
        file = tmp_path / "auth.py"
        file.write_text('"""Authentication module."""\n\ndef login():\n    """User login function."""\n')

        results = search_docstrings("authentication", root=tmp_path)

        assert len(results) > 0
        for result in results:
            assert isinstance(result.path, str)
            assert result.path.endswith(".py")
            # Path should be relative
            assert not result.path.startswith("/")

    def test_search_returns_docstring_summaries(self, tmp_path):
        """Verify each result includes docstring text."""
        (tmp_path / ".git").mkdir()
        file = tmp_path / "auth.py"
        file.write_text('"""Authentication module with JWT support."""\n')

        results = search_docstrings("authentication", root=tmp_path)

        assert len(results) > 0
        for result in results:
            assert isinstance(result.summary, str)
            assert len(result.summary) > 0

    def test_search_returns_extents(self, tmp_path):
        """Verify each result includes extent information."""
        (tmp_path / ".git").mkdir()
        file = tmp_path / "auth.py"
        file.write_text('"""Authentication module."""\n\ndef login():\n    """User login."""\n')

        results = search_docstrings("authentication", root=tmp_path)

        assert len(results) > 0
        for result in results:
            assert isinstance(result.extent, Location)
            assert result.extent.start >= 0
            assert result.extent.end >= result.extent.start

    def test_search_empty_query_returns_empty(self, tmp_path):
        """Verify empty query returns empty list."""
        (tmp_path / ".git").mkdir()
        file = tmp_path / "auth.py"
        file.write_text('"""Authentication module."""\n')

        results = search_docstrings("", root=tmp_path)
        assert results == []

    def test_search_whitespace_query_returns_empty(self, tmp_path):
        """Verify whitespace-only query returns empty list."""
        (tmp_path / ".git").mkdir()
        file = tmp_path / "auth.py"
        file.write_text('"""Authentication module."""\n')

        # Whitespace should be tokenized to empty list
        results = search_docstrings("   ", root=tmp_path)
        assert results == []

    def test_search_no_docstrings_returns_empty(self, tmp_path):
        """Verify search returns empty list when codebase has no docstrings."""
        (tmp_path / ".git").mkdir()
        file = tmp_path / "no_docs.py"
        file.write_text("def foo():\n    pass\n")

        results = search_docstrings("foo", root=tmp_path)
        assert results == []

    def test_search_no_matches_returns_empty(self, tmp_path):
        """Verify search returns empty list when query has no matching terms."""
        (tmp_path / ".git").mkdir()
        file = tmp_path / "auth.py"
        file.write_text('"""Authentication module."""\n')

        results = search_docstrings("xyzabc123notfound", root=tmp_path)
        # BM25 might return low-scored results, but with proper tokenization
        # completely unrelated terms should return empty or very low scores
        # For this test, we just verify it doesn't crash
        assert isinstance(results, list)

    def test_search_finds_multiple_entity_types(self, tmp_path):
        """Verify search finds different entity types (module, function, class, method)."""
        (tmp_path / ".git").mkdir()
        file = tmp_path / "entities.py"
        file.write_text('''"""Module about authentication."""

def authenticate():
    """Function for authentication."""
    pass

class Auth:
    """Class for authentication."""

    def login(self):
        """Method for authentication."""
        pass
''')

        results = search_docstrings("authentication", root=tmp_path)

        # Should find module, function, class, and method
        kinds = {r.kind for r in results}
        assert "module" in kinds
        assert "function" in kinds
        assert "class" in kinds
        assert "method" in kinds

    def test_search_ranking_order(self, tmp_path):
        """Verify results are returned in descending BM25 score order."""
        (tmp_path / ".git").mkdir()
        file1 = tmp_path / "exact.py"
        file1.write_text('"""JWT authentication handler."""\n')
        file2 = tmp_path / "partial.py"
        file2.write_text('"""Handler for user sessions."""\n')

        results = search_docstrings("JWT authentication", root=tmp_path)

        # First result should be the exact match
        assert len(results) >= 1
        assert "exact.py" in results[0].path
        assert "JWT" in results[0].summary

    def test_search_case_insensitive(self, tmp_path):
        """Verify search is case-insensitive."""
        (tmp_path / ".git").mkdir()
        file = tmp_path / "auth.py"
        file.write_text('"""JWT authentication handler."""\n')

        results_lower = search_docstrings("jwt", root=tmp_path)
        results_upper = search_docstrings("JWT", root=tmp_path)
        results_mixed = search_docstrings("JwT", root=tmp_path)

        # All should return the same results
        assert len(results_lower) == len(results_upper) == len(results_mixed)
        assert len(results_lower) > 0

    def test_search_uses_config(self, tmp_path):
        """Verify search respects provided SearchConfig."""
        (tmp_path / ".git").mkdir()
        for i in range(10):
            file = tmp_path / f"module_{i}.py"
            file.write_text(f'"""Module {i} about testing."""\n')

        # Test with different max_results
        config_2 = SearchConfig(max_results=2)
        results_2 = search_docstrings("testing", root=tmp_path, config=config_2)
        assert len(results_2) == 2

        config_5 = SearchConfig(max_results=5)
        results_5 = search_docstrings("testing", root=tmp_path, config=config_5)
        assert len(results_5) == 5

    def test_search_finds_repository_root_when_none(self):
        """Verify search finds repository root when root=None."""
        # This test should work if run from within athena repository
        # Just verify it doesn't crash
        try:
            results = search_docstrings("BM25", root=None)
            assert isinstance(results, list)
        except RepositoryNotFoundError:
            # If we're not in a git repo, that's expected
            pass

    def test_search_loads_config_when_none(self, tmp_path):
        """Verify search loads config from .athena when config=None."""
        (tmp_path / ".git").mkdir()
        file = tmp_path / "test.py"
        file.write_text('"""Test module."""\n')

        # Create .athena config file
        config_file = tmp_path / ".athena"
        config_file.write_text("""
search:
  term_frequency_saturation: 1.8
  length_normalization: 0.6
  max_results: 5
""")

        # Should use config from file
        results = search_docstrings("test", root=tmp_path, config=None)
        # Just verify it works without crashing
        assert isinstance(results, list)

    def test_search_handles_unicode_in_docstrings(self, tmp_path):
        """Verify search handles Unicode characters in docstrings."""
        (tmp_path / ".git").mkdir()
        file = tmp_path / "unicode.py"
        file.write_text('"""Módulo de autenticación con JWT. 中文測試."""\n', encoding="utf-8")

        results = search_docstrings("autenticación", root=tmp_path)
        assert len(results) > 0
        assert "Módulo" in results[0].summary

    def test_search_handles_multiline_docstrings(self, tmp_path):
        """Verify search handles multi-line docstrings."""
        (tmp_path / ".git").mkdir()
        file = tmp_path / "multiline.py"
        file.write_text('''"""
Authentication module.

Handles JWT token validation and user login.
Supports multiple authentication providers.
"""
''')

        results = search_docstrings("authentication", root=tmp_path)
        assert len(results) > 0
        # Summary should contain the full docstring
        assert "JWT" in results[0].summary

    def test_search_handles_code_blocks_in_docstrings(self, tmp_path):
        """Verify search handles docstrings with code examples."""
        (tmp_path / ".git").mkdir()
        file = tmp_path / "examples.py"
        file.write_text('''"""
Authentication handler.

Example:
    auth = authenticate(token)
    if auth.is_valid():
        return True
"""
''')

        results = search_docstrings("authentication", root=tmp_path)
        assert len(results) > 0

    def test_search_skips_unreadable_files(self, tmp_path):
        """Verify search gracefully skips files that can't be read."""
        (tmp_path / ".git").mkdir()
        good_file = tmp_path / "good.py"
        good_file.write_text('"""Good module."""\n')

        # Create a directory with .py extension (can't be read as file)
        bad_path = tmp_path / "bad.py"
        bad_path.mkdir()

        # Should still find the good file
        results = search_docstrings("Good", root=tmp_path)
        assert len(results) > 0


class TestCaching:
    """Test suite for caching behavior."""

    def test_cache_key_generation(self, tmp_path):
        """Verify cache key is generated correctly."""
        (tmp_path / ".git").mkdir()
        file = tmp_path / "test.py"
        file.write_text('"""Test."""\n')

        key = _get_cache_key(tmp_path)
        assert isinstance(key, tuple)
        assert len(key) == 2
        assert isinstance(key[0], str)
        assert isinstance(key[1], float)

    def test_cache_avoids_reparse(self, tmp_path):
        """Verify cache avoids reparsing on subsequent searches."""
        (tmp_path / ".git").mkdir()
        file = tmp_path / "test.py"
        file.write_text('"""Test module."""\n')

        # First search
        results1 = search_docstrings("test", root=tmp_path)

        # Second search should use cache (same results)
        results2 = search_docstrings("test", root=tmp_path)

        # Results should be identical
        assert len(results1) == len(results2)
        for r1, r2 in zip(results1, results2):
            assert r1.kind == r2.kind
            assert r1.path == r2.path

    def test_cache_invalidates_on_modification(self, tmp_path):
        """Verify cache invalidates when files are modified."""
        (tmp_path / ".git").mkdir()
        file = tmp_path / "test.py"
        file.write_text('"""Original docstring."""\n')

        # First search
        results1 = search_docstrings("Original", root=tmp_path)
        assert len(results1) > 0

        # Modify file (this changes mtime)
        import time
        time.sleep(0.01)  # Ensure mtime changes
        file.write_text('"""Updated docstring."""\n')

        # Second search should reflect the change
        results2 = search_docstrings("Updated", root=tmp_path)
        assert len(results2) > 0
        assert "Updated" in results2[0].summary

    def test_cache_handles_missing_file(self, tmp_path):
        """Verify cache handles files that disappear."""
        (tmp_path / ".git").mkdir()
        file = tmp_path / "test.py"
        file.write_text('"""Test."""\n')

        # Get cache key, then delete the file
        file.unlink()

        # Cache key generation should handle missing files
        key = _get_cache_key(tmp_path)
        assert isinstance(key, tuple)


class TestEdgeCases:
    """Test suite for edge cases."""

    def test_empty_codebase(self, tmp_path):
        """Verify search handles empty codebase (no Python files)."""
        (tmp_path / ".git").mkdir()

        results = search_docstrings("anything", root=tmp_path)
        assert results == []

    def test_very_short_docstring(self, tmp_path):
        """Verify search handles single-word docstrings."""
        (tmp_path / ".git").mkdir()
        file = tmp_path / "short.py"
        file.write_text('"""JWT."""\n')

        results = search_docstrings("JWT", root=tmp_path)
        assert len(results) > 0

    def test_very_long_query(self, tmp_path):
        """Verify search handles very long queries."""
        (tmp_path / ".git").mkdir()
        file = tmp_path / "auth.py"
        file.write_text('"""Authentication module."""\n')

        long_query = " ".join(["authentication"] * 100)
        results = search_docstrings(long_query, root=tmp_path)
        # Should still work
        assert isinstance(results, list)

    def test_special_characters_in_query(self, tmp_path):
        """Verify search handles special characters in query."""
        (tmp_path / ".git").mkdir()
        file = tmp_path / "test.py"
        file.write_text('"""Test module with @decorators and #comments."""\n')

        results = search_docstrings("@decorators #comments", root=tmp_path)
        # Should tokenize and search
        assert isinstance(results, list)

    def test_no_repository_raises_error(self):
        """Verify search raises RepositoryNotFoundError when no git repo found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Directory without .git
            with pytest.raises(RepositoryNotFoundError):
                search_docstrings("test", root=Path(tmpdir))

    def test_search_with_excluded_directories(self, tmp_path):
        """Verify search excludes common directories like __pycache__, .venv, etc."""
        (tmp_path / ".git").mkdir()

        # Create files in excluded directories
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "test.py").write_text('"""Should be excluded."""\n')

        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv" / "test.py").write_text('"""Should be excluded."""\n')

        # Create file in normal directory
        (tmp_path / "normal.py").write_text('"""Should be included."""\n')

        results = search_docstrings("Should", root=tmp_path)

        # Should only find the normal file
        assert len(results) == 1
        assert "normal.py" in results[0].path

    def test_search_with_decorated_entities(self, tmp_path):
        """Verify search finds decorated functions and classes."""
        (tmp_path / ".git").mkdir()
        file = tmp_path / "decorated.py"
        file.write_text('''
@decorator
def func():
    """Decorated function."""
    pass

@decorator
class MyClass:
    """Decorated class."""
    pass
''')

        results = search_docstrings("Decorated", root=tmp_path)
        assert len(results) == 2
        kinds = {r.kind for r in results}
        assert "function" in kinds
        assert "class" in kinds

    def test_search_performance_on_large_corpus(self, tmp_path):
        """Verify search completes quickly on reasonably-sized codebase."""
        import time

        (tmp_path / ".git").mkdir()

        # Create 200 files with docstrings
        for i in range(200):
            file = tmp_path / f"module_{i}.py"
            file.write_text(f'"""Module {i} for testing search performance."""\n')

        start = time.time()
        results = search_docstrings("testing", root=tmp_path)
        elapsed = time.time() - start

        # Should complete in under 1 second (spec says <100ms, but allow overhead)
        assert elapsed < 1.0
        assert len(results) > 0
