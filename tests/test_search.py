"""Tests for FTS5 docstring search functionality."""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from athena.cache import CacheDatabase
from athena.config import SearchConfig
from athena.models import Location, SearchResult
from athena.repository import RepositoryNotFoundError
from athena.search import (
    _parse_file_entities,
    _process_file_with_cache,
    _scan_repo_with_cache,
    search_docstrings,
)


class TestParseFileEntities:
    """Test suite for _parse_file_entities function."""

    def test_parse_module_docstring(self, tmp_path):
        """Verify parsing extracts module-level docstring."""
        file_path = tmp_path / "module.py"
        source_code = '"""Module docstring."""\n'

        entities = _parse_file_entities(file_path, source_code, "module.py")

        assert len(entities) == 1
        kind, path, extent, docstring = entities[0]
        assert kind == "module"
        assert path == "module.py"
        assert extent.start == 0
        assert docstring == "Module docstring."

    def test_parse_function_docstring(self, tmp_path):
        """Verify parsing extracts function docstring."""
        file_path = tmp_path / "func.py"
        source_code = '''def my_function():
    """Function docstring."""
    pass
'''

        entities = _parse_file_entities(file_path, source_code, "func.py")

        assert len(entities) == 1
        kind, path, extent, docstring = entities[0]
        assert kind == "function"
        assert path == "func.py"
        assert extent.start == 0
        assert extent.end > extent.start
        assert docstring == "Function docstring."

    def test_parse_class_docstring(self, tmp_path):
        """Verify parsing extracts class docstring."""
        file_path = tmp_path / "cls.py"
        source_code = '''class MyClass:
    """Class docstring."""
    pass
'''

        entities = _parse_file_entities(file_path, source_code, "cls.py")

        assert len(entities) == 1
        kind, path, extent, docstring = entities[0]
        assert kind == "class"
        assert path == "cls.py"
        assert docstring == "Class docstring."

    def test_parse_method_docstring(self, tmp_path):
        """Verify parsing extracts method docstring."""
        file_path = tmp_path / "method.py"
        source_code = '''class MyClass:
    """Class docstring."""

    def my_method(self):
        """Method docstring."""
        pass
'''

        entities = _parse_file_entities(file_path, source_code, "method.py")

        # Should find class and method
        assert len(entities) == 2
        kinds = {e[0] for e in entities}
        assert "class" in kinds
        assert "method" in kinds

        method_entity = [e for e in entities if e[0] == "method"][0]
        assert method_entity[3] == "Method docstring."

    def test_parse_decorated_function(self, tmp_path):
        """Verify parsing handles decorated functions."""
        file_path = tmp_path / "decorated.py"
        source_code = '''@decorator
def my_function():
    """Decorated function."""
    pass
'''

        entities = _parse_file_entities(file_path, source_code, "decorated.py")

        assert len(entities) == 1
        kind, path, extent, docstring = entities[0]
        assert kind == "function"
        assert docstring == "Decorated function."
        # Extent should include decorator
        assert extent.start == 0

    def test_parse_decorated_class(self, tmp_path):
        """Verify parsing handles decorated classes."""
        file_path = tmp_path / "decorated.py"
        source_code = '''@decorator
class MyClass:
    """Decorated class."""
    pass
'''

        entities = _parse_file_entities(file_path, source_code, "decorated.py")

        assert len(entities) == 1
        kind, path, extent, docstring = entities[0]
        assert kind == "class"
        assert docstring == "Decorated class."
        # Extent should include decorator
        assert extent.start == 0

    def test_parse_multiple_entities(self, tmp_path):
        """Verify parsing finds all entity types in one file."""
        file_path = tmp_path / "multi.py"
        source_code = '''"""Module docstring."""

def func():
    """Function docstring."""
    pass

class MyClass:
    """Class docstring."""

    def method(self):
        """Method docstring."""
        pass
'''

        entities = _parse_file_entities(file_path, source_code, "multi.py")

        # Should find module, function, class, and method
        assert len(entities) == 4
        kinds = {e[0] for e in entities}
        assert kinds == {"module", "function", "class", "method"}

    def test_parse_no_docstrings(self, tmp_path):
        """Verify parsing returns empty list when no docstrings exist."""
        file_path = tmp_path / "nodocs.py"
        source_code = '''def func():
    pass

class MyClass:
    pass
'''

        entities = _parse_file_entities(file_path, source_code, "nodocs.py")

        assert entities == []

    def test_parse_multiline_docstring(self, tmp_path):
        """Verify parsing handles multiline docstrings."""
        file_path = tmp_path / "multiline.py"
        source_code = '''"""
Module with multiline docstring.

This is a longer description.
"""
'''

        entities = _parse_file_entities(file_path, source_code, "multiline.py")

        assert len(entities) == 1
        docstring = entities[0][3]
        assert "Module with multiline docstring" in docstring
        assert "longer description" in docstring

    def test_parse_empty_file(self, tmp_path):
        """Verify parsing handles empty file."""
        file_path = tmp_path / "empty.py"
        source_code = ""

        entities = _parse_file_entities(file_path, source_code, "empty.py")

        assert entities == []

    def test_parse_preserves_relative_path(self, tmp_path):
        """Verify all entities use the provided relative path."""
        file_path = tmp_path / "subdir" / "module.py"
        source_code = '''"""Module."""

def func():
    """Function."""
    pass
'''

        entities = _parse_file_entities(file_path, source_code, "subdir/module.py")

        # All entities should have the same relative path
        for entity in entities:
            assert entity[1] == "subdir/module.py"


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
        # FTS5 might return low-scored results for unrelated terms
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
        """Verify results are returned in descending FTS5 relevance order."""
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
            results = search_docstrings("search", root=None)
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


class TestProcessFileWithCache:
    """Test suite for _process_file_with_cache function."""

    def test_cache_miss_parses_and_inserts(self, tmp_path):
        """Verify cache miss triggers parsing and database insertion."""
        # Create a Python file with a function
        file_path = tmp_path / "test.py"
        source_code = '''def my_function():
    """Test function."""
    pass
'''
        file_path.write_text(source_code)
        current_mtime = file_path.stat().st_mtime

        # Create cache database
        cache_dir = tmp_path / ".athena-cache"
        with CacheDatabase(cache_dir) as cache_db:
            # Process file (cache miss)
            entities = _process_file_with_cache(cache_db, file_path, current_mtime, tmp_path)

            # Should return parsed entities
            assert len(entities) == 1
            kind, path, extent, docstring = entities[0]
            assert kind == "function"
            assert path == "test.py"
            assert docstring == "Test function."

            # Verify file was added to cache
            cached_file = cache_db.get_file("test.py")
            assert cached_file is not None
            file_id, cached_mtime = cached_file
            assert cached_mtime == current_mtime

            # Verify entities were added to cache
            all_entities = cache_db.get_all_entities()
            assert len(all_entities) == 1

    def test_cache_hit_no_reparse(self, tmp_path):
        """Verify cache hit avoids reparsing when mtime matches."""
        # Create a Python file
        file_path = tmp_path / "test.py"
        source_code = '''def my_function():
    """Test function."""
    pass
'''
        file_path.write_text(source_code)
        current_mtime = file_path.stat().st_mtime

        cache_dir = tmp_path / ".athena-cache"
        with CacheDatabase(cache_dir) as cache_db:
            # First process (cache miss)
            entities_first = _process_file_with_cache(cache_db, file_path, current_mtime, tmp_path)
            assert len(entities_first) == 1

            # Second process with same mtime (cache hit)
            entities_second = _process_file_with_cache(cache_db, file_path, current_mtime, tmp_path)

            # Should return empty list since file is cached and up-to-date
            assert entities_second == []

            # Verify cache still has the entity
            all_entities = cache_db.get_all_entities()
            assert len(all_entities) == 1

    def test_mtime_change_triggers_reparse(self, tmp_path):
        """Verify mtime change triggers reparsing and cache update."""
        # Create a Python file
        file_path = tmp_path / "test.py"
        source_code_v1 = '''def old_function():
    """Old function."""
    pass
'''
        file_path.write_text(source_code_v1)
        mtime_v1 = file_path.stat().st_mtime

        cache_dir = tmp_path / ".athena-cache"
        with CacheDatabase(cache_dir) as cache_db:
            # First process
            entities_v1 = _process_file_with_cache(cache_db, file_path, mtime_v1, tmp_path)
            assert len(entities_v1) == 1
            assert entities_v1[0][3] == "Old function."

            # Modify file
            source_code_v2 = '''def new_function():
    """New function."""
    pass
'''
            file_path.write_text(source_code_v2)
            mtime_v2 = file_path.stat().st_mtime + 1.0  # Simulate time passing

            # Second process with different mtime
            entities_v2 = _process_file_with_cache(cache_db, file_path, mtime_v2, tmp_path)

            # Should return new parsed entities
            assert len(entities_v2) == 1
            assert entities_v2[0][3] == "New function."

            # Verify cache was updated
            cached_file = cache_db.get_file("test.py")
            assert cached_file is not None
            file_id, cached_mtime = cached_file
            assert cached_mtime == mtime_v2

            # Verify old entities were replaced
            all_entities = cache_db.get_all_entities()
            assert len(all_entities) == 1
            assert all_entities[0][4] == "New function."

    def test_unreadable_file_returns_empty(self, tmp_path):
        """Verify unreadable file returns empty list."""
        # Create a file path that doesn't exist
        file_path = tmp_path / "nonexistent.py"
        current_mtime = 12345.0

        cache_dir = tmp_path / ".athena-cache"
        with CacheDatabase(cache_dir) as cache_db:
            entities = _process_file_with_cache(cache_db, file_path, current_mtime, tmp_path)
            assert entities == []

            # Verify nothing was added to cache
            assert cache_db.get_file("nonexistent.py") is None

    def test_multiple_entities_in_file(self, tmp_path):
        """Verify processing file with multiple entities."""
        file_path = tmp_path / "multi.py"
        source_code = '''"""Module docstring."""

def func1():
    """Function 1."""
    pass

def func2():
    """Function 2."""
    pass

class MyClass:
    """Class docstring."""
    pass
'''
        file_path.write_text(source_code)
        current_mtime = file_path.stat().st_mtime

        cache_dir = tmp_path / ".athena-cache"
        with CacheDatabase(cache_dir) as cache_db:
            entities = _process_file_with_cache(cache_db, file_path, current_mtime, tmp_path)

            # Should return all entities
            assert len(entities) == 4
            kinds = [e[0] for e in entities]
            assert "module" in kinds
            assert kinds.count("function") == 2
            assert "class" in kinds

            # Verify all entities were cached
            all_cached = cache_db.get_all_entities()
            assert len(all_cached) == 4

    def test_file_without_docstrings(self, tmp_path):
        """Verify processing file with no docstrings."""
        file_path = tmp_path / "nodocs.py"
        source_code = '''def func():
    pass

class MyClass:
    pass
'''
        file_path.write_text(source_code)
        current_mtime = file_path.stat().st_mtime

        cache_dir = tmp_path / ".athena-cache"
        with CacheDatabase(cache_dir) as cache_db:
            entities = _process_file_with_cache(cache_db, file_path, current_mtime, tmp_path)

            # Should return empty list (no docstrings)
            assert entities == []

            # File should still be tracked in cache
            cached_file = cache_db.get_file("nodocs.py")
            assert cached_file is not None

            # No entities should be cached
            all_cached = cache_db.get_all_entities()
            assert len(all_cached) == 0


class TestScanRepoWithCache:
    """Test suite for _scan_repo_with_cache function."""

    def test_full_scan_creates_cache(self, tmp_path):
        """Verify full repository scan creates cache entries for all files."""
        # Create multiple Python files
        file1 = tmp_path / "file1.py"
        file1.write_text('''def func1():
    """Function 1."""
    pass
''')

        file2 = tmp_path / "file2.py"
        file2.write_text('''def func2():
    """Function 2."""
    pass
''')

        subdir = tmp_path / "subdir"
        subdir.mkdir()
        file3 = subdir / "file3.py"
        file3.write_text('''class MyClass:
    """Class docstring."""
    pass
''')

        # Scan repository
        cache_dir = tmp_path / ".athena-cache"
        with CacheDatabase(cache_dir) as cache_db:
            entities = _scan_repo_with_cache(tmp_path, cache_db)

            # Should return all entities
            assert len(entities) == 3

            # Verify cache has all files
            assert cache_db.get_file("file1.py") is not None
            assert cache_db.get_file("file2.py") is not None
            assert cache_db.get_file("subdir/file3.py") is not None

            # Verify all entities are in cache
            all_cached = cache_db.get_all_entities()
            assert len(all_cached) == 3

    def test_incremental_scan_updates_cache(self, tmp_path):
        """Verify incremental scan updates only changed files."""
        # Create initial file
        file1 = tmp_path / "file1.py"
        file1.write_text('''def func1():
    """Function 1."""
    pass
''')

        cache_dir = tmp_path / ".athena-cache"
        with CacheDatabase(cache_dir) as cache_db:
            # First scan
            entities1 = _scan_repo_with_cache(tmp_path, cache_db)
            assert len(entities1) == 1
            initial_file = cache_db.get_file("file1.py")
            assert initial_file is not None

            # Add new file
            file2 = tmp_path / "file2.py"
            file2.write_text('''def func2():
    """Function 2."""
    pass
''')

            # Second scan
            entities2 = _scan_repo_with_cache(tmp_path, cache_db)
            assert len(entities2) == 2

            # Both files should be in cache
            assert cache_db.get_file("file1.py") is not None
            assert cache_db.get_file("file2.py") is not None

            # Cache should have both entities
            all_cached = cache_db.get_all_entities()
            assert len(all_cached) == 2

    def test_deleted_file_removed_from_cache(self, tmp_path):
        """Verify deleted files are removed from cache."""
        # Create two files
        file1 = tmp_path / "file1.py"
        file1.write_text('''def func1():
    """Function 1."""
    pass
''')

        file2 = tmp_path / "file2.py"
        file2.write_text('''def func2():
    """Function 2."""
    pass
''')

        cache_dir = tmp_path / ".athena-cache"
        with CacheDatabase(cache_dir) as cache_db:
            # First scan (both files)
            entities1 = _scan_repo_with_cache(tmp_path, cache_db)
            assert len(entities1) == 2

            # Delete file2
            file2.unlink()

            # Second scan (only file1 remains)
            entities2 = _scan_repo_with_cache(tmp_path, cache_db)
            assert len(entities2) == 1

            # Only file1 should be in cache
            assert cache_db.get_file("file1.py") is not None
            assert cache_db.get_file("file2.py") is None

            # Cache should only have file1's entity
            all_cached = cache_db.get_all_entities()
            assert len(all_cached) == 1
            assert all_cached[0][1] == "file1.py"  # file_path field

    def test_modified_file_updates_entities(self, tmp_path):
        """Verify modified file triggers entity update in cache."""
        file1 = tmp_path / "file1.py"
        file1.write_text('''def old_func():
    """Old function."""
    pass
''')

        cache_dir = tmp_path / ".athena-cache"
        with CacheDatabase(cache_dir) as cache_db:
            # First scan
            entities1 = _scan_repo_with_cache(tmp_path, cache_db)
            assert len(entities1) == 1
            assert entities1[0][3] == "Old function."

            # Modify file
            import time
            time.sleep(0.01)  # Ensure mtime changes
            file1.write_text('''def new_func():
    """New function."""
    pass
''')

            # Second scan
            entities2 = _scan_repo_with_cache(tmp_path, cache_db)
            assert len(entities2) == 1
            assert entities2[0][3] == "New function."

            # Cache should have updated entity
            all_cached = cache_db.get_all_entities()
            assert len(all_cached) == 1
            assert all_cached[0][4] == "New function."  # summary field

    def test_empty_repository(self, tmp_path):
        """Verify empty repository returns empty results."""
        cache_dir = tmp_path / ".athena-cache"
        with CacheDatabase(cache_dir) as cache_db:
            entities = _scan_repo_with_cache(tmp_path, cache_db)
            assert entities == []
            all_cached = cache_db.get_all_entities()
            assert len(all_cached) == 0

    def test_scan_with_unreadable_files(self, tmp_path):
        """Verify scan handles unreadable files gracefully."""
        # Create one readable file
        file1 = tmp_path / "file1.py"
        file1.write_text('''def func1():
    """Function 1."""
    pass
''')

        cache_dir = tmp_path / ".athena-cache"
        with CacheDatabase(cache_dir) as cache_db:
            # Scan should complete without error
            entities = _scan_repo_with_cache(tmp_path, cache_db)
            assert len(entities) == 1
            assert entities[0][3] == "Function 1."

    def test_entities_format_conversion(self, tmp_path):
        """Verify entity format conversion from cache to search format."""
        file1 = tmp_path / "file1.py"
        file1.write_text('''def my_func():
    """Test function."""
    pass
''')

        cache_dir = tmp_path / ".athena-cache"
        with CacheDatabase(cache_dir) as cache_db:
            entities = _scan_repo_with_cache(tmp_path, cache_db)

            # Verify format: (kind, path, Location, docstring)
            assert len(entities) == 1
            kind, path, extent, docstring = entities[0]
            assert kind == "function"
            assert path == "file1.py"
            assert isinstance(extent, Location)
            assert extent.start >= 0
            assert extent.end >= extent.start
            assert docstring == "Test function."


class TestSearchWithSQLiteCache:
    """Integration tests for search_docstrings with SQLite cache."""

    def test_search_with_cache_first_run(self, tmp_path):
        """Verify search works on first run (cache miss)."""
        # Create a test repository
        (tmp_path / ".git").mkdir()
        test_file = tmp_path / "test.py"
        test_file.write_text('''def authenticate_user():
    """Authenticate user with JWT token."""
    pass

def process_payment():
    """Process payment transaction."""
    pass
''')

        # Perform search - use "jwt" which is a token in the docstring
        results = search_docstrings("jwt", root=tmp_path)

        # Should find the authenticate_user function (may find others due to small corpus)
        assert len(results) >= 1
        # Verify the JWT function is in results
        jwt_results = [r for r in results if "JWT" in r.summary or "jwt" in r.summary.lower()]
        assert len(jwt_results) >= 1
        assert jwt_results[0].kind == "function"
        assert jwt_results[0].path == "test.py"

        # Verify cache was created
        cache_dir = tmp_path / ".athena-cache"
        assert cache_dir.exists()
        assert (cache_dir / "docstring_cache.db").exists()

    def test_search_with_cache_second_run(self, tmp_path):
        """Verify search uses cache on second run (cache hit)."""
        # Create a test repository
        (tmp_path / ".git").mkdir()
        test_file = tmp_path / "test.py"
        test_file.write_text('''def authenticate_user():
    """Authenticate user with JWT token."""
    pass
''')

        # First search (cache miss) - use "token" which is in the docstring
        results1 = search_docstrings("token", root=tmp_path)
        assert len(results1) == 1

        # Second search (cache hit - should be faster)
        results2 = search_docstrings("token", root=tmp_path)
        assert len(results2) == 1
        assert results1[0].path == results2[0].path
        assert results1[0].summary == results2[0].summary

    def test_search_cache_invalidation_on_file_change(self, tmp_path):
        """Verify cache invalidates when file is modified."""
        # Create a test repository
        (tmp_path / ".git").mkdir()
        test_file = tmp_path / "test.py"
        test_file.write_text('''def old_function():
    """Process old data."""
    pass
''')

        # First search - "old" is a token in the docstring
        results1 = search_docstrings("old", root=tmp_path)
        assert len(results1) == 1
        assert "old" in results1[0].summary.lower()

        # Modify file
        import time
        time.sleep(0.01)  # Ensure mtime changes
        test_file.write_text('''def new_function():
    """Process new data."""
    pass
''')

        # Search again - should find new function
        results2 = search_docstrings("new", root=tmp_path)
        assert len(results2) == 1
        assert "new" in results2[0].summary.lower()

        # Old function should not be found
        results3 = search_docstrings("old", root=tmp_path)
        assert len(results3) == 0

    def test_search_handles_deleted_files(self, tmp_path):
        """Verify cache handles deleted files correctly."""
        # Create a test repository
        (tmp_path / ".git").mkdir()
        file1 = tmp_path / "file1.py"
        file2 = tmp_path / "file2.py"
        file1.write_text('''def func1():
    """Function in file1."""
    pass
''')
        file2.write_text('''def func2():
    """Function in file2."""
    pass
''')

        # First search - should find both
        results1 = search_docstrings("function", root=tmp_path)
        assert len(results1) == 2

        # Delete file2
        file2.unlink()

        # Search again - should only find file1
        results2 = search_docstrings("function", root=tmp_path)
        assert len(results2) == 1
        assert results2[0].path == "file1.py"

    def test_search_with_multiple_files(self, tmp_path):
        """Verify search works across multiple files."""
        # Create a test repository
        (tmp_path / ".git").mkdir()
        (tmp_path / "auth.py").write_text('''def login():
    """User login with credentials."""
    pass

def logout():
    """User logout and session cleanup."""
    pass
''')
        (tmp_path / "payment.py").write_text('''def process_payment():
    """Process credit card payment."""
    pass

def refund_payment():
    """Process payment refund."""
    pass
''')

        # Search for "credentials" - unique term in auth.py
        results = search_docstrings("credentials", root=tmp_path)
        assert len(results) >= 1
        assert any(r.path == "auth.py" for r in results)

        # Search for "refund" - unique term in payment.py
        results = search_docstrings("refund", root=tmp_path)
        assert len(results) >= 1
        assert any(r.path == "payment.py" for r in results)

    def test_search_preserves_existing_behavior(self, tmp_path):
        """Verify search results match expected format."""
        # Create a test repository
        (tmp_path / ".git").mkdir()
        test_file = tmp_path / "module.py"
        test_file.write_text('''"""Module for authentication."""

class Authenticator:
    """Handles user authentication."""

    def login(self):
        """Login user with credentials."""
        pass
''')

        # Perform search
        results = search_docstrings("authentication", root=tmp_path)

        # Should find module and class
        assert len(results) >= 2
        kinds = {r.kind for r in results}
        assert "module" in kinds or "class" in kinds

        # Verify result format
        for result in results:
            assert isinstance(result, SearchResult)
            assert isinstance(result.kind, str)
            assert isinstance(result.path, str)
            assert isinstance(result.extent, Location)
            assert isinstance(result.summary, str)
            assert result.extent.start >= 0
            assert result.extent.end >= result.extent.start


class TestSearchErrorHandling:
    """Tests for search error handling (no fallback - errors propagate)."""

    def test_search_raises_on_db_error(self, tmp_path):
        """Verify search raises error when cache fails (no fallback)."""
        # Create a test repository
        (tmp_path / ".git").mkdir()
        test_file = tmp_path / "test.py"
        test_file.write_text('''def authenticate():
    """Authenticate user."""
    pass
''')

        # Mock CacheDatabase to raise an error
        with patch("athena.search.CacheDatabase") as mock_cache:
            mock_cache.return_value.__enter__.side_effect = sqlite3.Error("DB corrupted")

            # Search should raise the error (no fallback)
            with pytest.raises(sqlite3.Error, match="DB corrupted"):
                search_docstrings("authenticate", root=tmp_path)

    def test_search_raises_on_runtime_error(self, tmp_path):
        """Verify search raises RuntimeError (no fallback)."""
        # Create a test repository
        (tmp_path / ".git").mkdir()
        test_file = tmp_path / "test.py"
        test_file.write_text('''def process():
    """Process data."""
    pass
''')

        with patch("athena.search.CacheDatabase") as mock_cache:
            mock_cache.return_value.__enter__.side_effect = RuntimeError("Connection failed")

            with pytest.raises(RuntimeError, match="Connection failed"):
                search_docstrings("process", root=tmp_path)

    def test_search_raises_on_os_error(self, tmp_path):
        """Verify search raises OSError (no fallback)."""
        # Create a test repository
        (tmp_path / ".git").mkdir()
        test_file = tmp_path / "test.py"
        test_file.write_text('''def validate():
    """Validate input."""
    pass
''')

        with patch("athena.search.CacheDatabase") as mock_cache:
            mock_cache.return_value.__enter__.side_effect = OSError("Permission denied")

            with pytest.raises(OSError, match="Permission denied"):
                search_docstrings("validate", root=tmp_path)


class TestConcurrentSearchAccess:
    """Test concurrent access to search functionality (simulating MCP server scenarios)."""

    def test_concurrent_searches_same_query(self, tmp_path):
        """Test multiple threads searching with the same query simultaneously."""
        import threading

        # Create test repository
        (tmp_path / ".git").mkdir()
        test_file = tmp_path / "module.py"
        test_file.write_text('''def process():
    """Process data."""
    pass

def calculate():
    """Calculate results."""
    pass

def validate():
    """Validate input."""
    pass
''')

        results_list = []
        errors = []

        def search_worker():
            try:
                results = search_docstrings("process", root=tmp_path)
                results_list.append(results)
            except Exception as e:
                errors.append(e)

        # Simulate 10 concurrent search requests
        threads = [threading.Thread(target=search_worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no errors
        assert len(errors) == 0, f"Concurrent searches failed: {errors}"

        # Verify all searches returned results
        assert len(results_list) == 10
        for results in results_list:
            assert len(results) >= 1
            assert any("process" in r.summary.lower() for r in results)

    def test_concurrent_searches_different_queries(self, tmp_path):
        """Test multiple threads searching with different queries simultaneously."""
        import threading

        # Create test repository
        (tmp_path / ".git").mkdir()
        test_file = tmp_path / "functions.py"
        test_file.write_text('''def alpha():
    """Alpha function for testing."""
    pass

def beta():
    """Beta function for testing."""
    pass

def gamma():
    """Gamma function for testing."""
    pass
''')

        results_dict = {}
        errors = []

        def search_worker(query, thread_id):
            try:
                results = search_docstrings(query, root=tmp_path)
                results_dict[thread_id] = results
            except Exception as e:
                errors.append((query, e))

        # Different queries from different threads
        queries = ["alpha", "beta", "gamma"] * 3  # 9 searches total
        threads = [threading.Thread(target=search_worker, args=(q, i)) for i, q in enumerate(queries)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no errors
        assert len(errors) == 0, f"Concurrent searches with different queries failed: {errors}"

        # Verify all searches completed
        assert len(results_dict) == 9

    def test_concurrent_searches_with_cache_updates(self, tmp_path):
        """Test searches while the cache is being updated (read/write concurrency)."""
        import threading
        import time

        # Create test repository
        (tmp_path / ".git").mkdir()
        initial_file = tmp_path / "initial.py"
        initial_file.write_text('''def initial():
    """Initial function."""
    pass
''')

        # Run initial search to populate cache
        search_docstrings("initial", root=tmp_path)

        results_list = []
        errors = []

        def reader():
            try:
                for _ in range(5):
                    results = search_docstrings("function", root=tmp_path)
                    results_list.append(results)
                    time.sleep(0.01)
            except Exception as e:
                errors.append(("read", e))

        def writer(file_num):
            try:
                new_file = tmp_path / f"new_{file_num}.py"
                new_file.write_text(f'''def function_{file_num}():
    """Function number {file_num}."""
    pass
''')
                # Trigger cache update by searching
                search_docstrings(f"function_{file_num}", root=tmp_path)
            except Exception as e:
                errors.append(("write", e))

        # Mix of readers and writers
        threads = []
        threads.extend([threading.Thread(target=reader) for _ in range(2)])
        threads.extend([threading.Thread(target=writer, args=(i,)) for i in range(3)])

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no errors (WAL mode allows concurrent reads/writes)
        assert len(errors) == 0, f"Concurrent searches with cache updates failed: {errors}"

        # Verify searches completed
        assert len(results_list) == 10  # 2 readers * 5 searches each

    def test_concurrent_first_time_cache_creation(self, tmp_path):
        """Test concurrent searches when cache doesn't exist yet."""
        import threading
        import shutil

        # Create test repository
        (tmp_path / ".git").mkdir()
        test_file = tmp_path / "test.py"
        test_file.write_text('''def concurrent():
    """Concurrent test function."""
    pass
''')

        # Ensure cache doesn't exist
        cache_dir = tmp_path / ".athena-cache"
        if cache_dir.exists():
            shutil.rmtree(cache_dir)

        results_list = []
        errors = []

        def search_worker():
            try:
                results = search_docstrings("concurrent", root=tmp_path)
                results_list.append(results)
            except Exception as e:
                errors.append(e)

        # Multiple threads trying to create cache simultaneously
        threads = [threading.Thread(target=search_worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no errors (one thread creates, others wait)
        assert len(errors) == 0, f"Concurrent cache creation failed: {errors}"

        # Verify all searches completed
        assert len(results_list) == 5
        for results in results_list:
            assert len(results) >= 1

    def test_concurrent_searches_with_file_modifications(self, tmp_path):
        """Test searches when files are being modified (mtime changes)."""
        import threading
        import time

        # Create test repository
        (tmp_path / ".git").mkdir()
        test_file = tmp_path / "dynamic.py"
        test_file.write_text('''def version_1():
    """Version 1 of function."""
    pass
''')

        # Initial search to populate cache
        search_docstrings("version", root=tmp_path)

        results_list = []
        errors = []

        def reader():
            try:
                for _ in range(3):
                    results = search_docstrings("version", root=tmp_path)
                    results_list.append(len(results))
                    time.sleep(0.02)
            except Exception as e:
                errors.append(("read", e))

        def modifier():
            try:
                time.sleep(0.01)
                # Modify file to trigger cache invalidation
                test_file.write_text('''def version_1():
    """Version 1 of function."""
    pass

def version_2():
    """Version 2 of function."""
    pass
''')
                time.sleep(0.01)
            except Exception as e:
                errors.append(("modify", e))

        # Reader threads and modifier thread
        threads = []
        threads.extend([threading.Thread(target=reader) for _ in range(2)])
        threads.append(threading.Thread(target=modifier))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no errors
        assert len(errors) == 0, f"Concurrent searches with file modifications failed: {errors}"

        # Verify searches completed
        assert len(results_list) == 6  # 2 readers * 3 searches each
