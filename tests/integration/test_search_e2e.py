"""End-to-end tests for search command."""

import json
import subprocess
import tempfile
import time
from pathlib import Path


class TestSearchE2E:
    """End-to-end tests for search command via CLI."""

    def test_search_athena_codebase_for_parsing(self):
        """Test search on actual athena codebase for parsing-related entities."""
        result = subprocess.run(
            ["uv", "run", "-m", "athena", "search", "--json", "parse Python code"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        data = json.loads(result.stdout)

        # Should find parsing-related entities
        assert len(data) > 0
        assert any("parser" in e["path"].lower() for e in data)

    def test_search_athena_codebase_for_docstring_extraction(self):
        """Test search for docstring extraction functionality."""
        result = subprocess.run(
            ["uv", "run", "-m", "athena", "search", "--json", "extract docstring"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        data = json.loads(result.stdout)

        # Should find docstring-related entities
        assert len(data) > 0
        # Should include summary field
        for entity in data:
            assert "summary" in entity
            assert isinstance(entity["summary"], str)

    def test_search_athena_codebase_for_repository_operations(self):
        """Test search for repository-related functionality."""
        result = subprocess.run(
            ["uv", "run", "-m", "athena", "search", "--json", "find repository root"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        data = json.loads(result.stdout)

        # Should find repository-related entities
        assert len(data) > 0
        assert any("repository" in e["path"].lower() for e in data)

    def test_search_multi_module_results(self):
        """Test that search returns results from multiple modules."""
        result = subprocess.run(
            ["uv", "run", "-m", "athena", "search", "--json", "entity"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        data = json.loads(result.stdout)

        # Should find entities across multiple files
        assert len(data) > 0
        paths = {e["path"] for e in data}
        # Should have results from more than one file
        assert len(paths) > 1

    def test_search_nested_entities(self):
        """Test search finds methods within classes."""
        result = subprocess.run(
            ["uv", "run", "-m", "athena", "search", "--json", "extract entities"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        data = json.loads(result.stdout)

        # Should find various entity types including methods
        kinds = {e["kind"] for e in data}
        assert len(kinds) > 1  # Multiple types of entities

    def test_search_cross_cutting_concerns(self):
        """Test search across multiple files for cross-cutting functionality."""
        result = subprocess.run(
            ["uv", "run", "-m", "athena", "search", "--json", "hash"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        data = json.loads(result.stdout)

        # Should find hash-related entities
        assert len(data) > 0

    def test_search_performance_on_athena_codebase(self):
        """Test that search completes quickly on athena codebase (~200 entities)."""
        start_time = time.time()

        result = subprocess.run(
            ["uv", "run", "-m", "athena", "search", "--json", "function"],
            capture_output=True,
            text=True
        )

        elapsed = time.time() - start_time

        assert result.returncode == 0
        # Should complete reasonably quickly (allow more than 100ms for CLI overhead)
        # The actual search function should be <100ms, but CLI has startup overhead
        assert elapsed < 5.0  # 5 seconds is very generous for E2E test

    def test_search_json_output_structure(self):
        """Test that JSON output has correct structure."""
        result = subprocess.run(
            ["uv", "run", "-m", "athena", "search", "--json", "parse"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        data = json.loads(result.stdout)

        # Should be a list
        assert isinstance(data, list)

        if len(data) > 0:
            entity = data[0]
            # Should have required fields
            assert "kind" in entity
            assert "path" in entity
            assert "extent" in entity
            assert "summary" in entity
            # Should NOT have score field
            assert "score" not in entity
            # Extent should have start and end
            assert "start" in entity["extent"]
            assert "end" in entity["extent"]

    def test_search_table_output_format(self):
        """Test that table output is human-readable."""
        result = subprocess.run(
            ["uv", "run", "-m", "athena", "search", "parse"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        # Should have table headers
        assert "Kind" in result.stdout
        assert "Path" in result.stdout
        assert "Extent" in result.stdout
        assert "Summary" in result.stdout
        # Should NOT have Score column
        assert "Score" not in result.stdout

    def test_search_no_matches_returns_empty(self):
        """Test that search with no matches returns empty results."""
        result = subprocess.run(
            ["uv", "run", "-m", "athena", "search", "--json", "xyzabc123notfound"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data == []

    def test_search_empty_query(self):
        """Test search with empty query."""
        result = subprocess.run(
            ["uv", "run", "-m", "athena", "search", "--json", ""],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data == []

    def test_search_max_results_flag(self):
        """Test --max-results flag limits output."""
        # Search for common term that should match many entities
        result = subprocess.run(
            ["uv", "run", "-m", "athena", "search", "--json", "--max-results", "3", "function"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        data = json.loads(result.stdout)
        # Should respect max_results limit
        assert len(data) <= 3

    def test_search_max_results_short_flag(self):
        """Test -k short flag for max results."""
        result = subprocess.run(
            ["uv", "run", "-m", "athena", "search", "--json", "-k", "5", "entity"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data) <= 5

    def test_search_case_insensitive(self):
        """Test that search is case-insensitive."""
        # Search with different cases
        result_lower = subprocess.run(
            ["uv", "run", "-m", "athena", "search", "--json", "parser"],
            capture_output=True,
            text=True
        )
        result_upper = subprocess.run(
            ["uv", "run", "-m", "athena", "search", "--json", "PARSER"],
            capture_output=True,
            text=True
        )

        assert result_lower.returncode == 0
        assert result_upper.returncode == 0

        data_lower = json.loads(result_lower.stdout)
        data_upper = json.loads(result_upper.stdout)

        # Should return same results regardless of case
        assert len(data_lower) == len(data_upper)

    def test_search_code_identifiers(self):
        """Test search with code identifiers (snake_case, camelCase)."""
        result = subprocess.run(
            ["uv", "run", "-m", "athena", "search", "--json", "find_repository_root"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        data = json.loads(result.stdout)
        # Should find entities related to repository finding
        assert len(data) > 0

    def test_search_natural_language_query(self):
        """Test search with natural language query."""
        result = subprocess.run(
            ["uv", "run", "-m", "athena", "search", "--json", "how do I parse a Python file"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        data = json.loads(result.stdout)
        # Should find parsing-related entities
        assert len(data) > 0


class TestSearchEdgeCases:
    """Edge case tests for search command."""

    def test_search_empty_codebase(self):
        """Test search on empty codebase."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".git").mkdir()

            result = subprocess.run(
                ["uv", "run", "-m", "athena", "search", "--json", "test"],
                cwd=repo_root,
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            data = json.loads(result.stdout)
            assert data == []

    def test_search_codebase_no_docstrings(self):
        """Test search on codebase with no docstrings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".git").mkdir()
            test_file = repo_root / "test.py"
            test_file.write_text(
                """def foo():
    return 1

def bar():
    return 2
"""
            )

            result = subprocess.run(
                ["uv", "run", "-m", "athena", "search", "--json", "test"],
                cwd=repo_root,
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            data = json.loads(result.stdout)
            # Should return empty since no docstrings to search
            assert data == []

    def test_search_very_short_docstrings(self):
        """Test search with single-word docstrings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".git").mkdir()
            test_file = repo_root / "test.py"
            test_file.write_text(
                '''def foo():
    """Test."""
    return 1
'''
            )

            result = subprocess.run(
                ["uv", "run", "-m", "athena", "search", "--json", "test"],
                cwd=repo_root,
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            data = json.loads(result.stdout)
            assert len(data) == 1
            assert data[0]["summary"] == "Test."

    def test_search_very_long_docstrings(self):
        """Test search with multi-paragraph docstrings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".git").mkdir()
            test_file = repo_root / "test.py"
            # Create a very long docstring
            long_docstring = "Search functionality. " + "Additional info. " * 50
            test_file.write_text(
                f'''def search_function():
    """{long_docstring}"""
    return 1
'''
            )

            result = subprocess.run(
                ["uv", "run", "-m", "athena", "search", "--json", "search"],
                cwd=repo_root,
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            data = json.loads(result.stdout)
            assert len(data) == 1
            # Summary should include the full docstring (JSON output)
            assert "Search functionality" in data[0]["summary"]

    def test_search_unicode_in_docstrings(self):
        """Test search with Unicode characters in docstrings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".git").mkdir()
            test_file = repo_root / "test.py"
            test_file.write_text(
                '''def foo():
    """Handle UTF-8: café, naïve, 日本語."""
    return 1
''',
                encoding="utf-8"
            )

            result = subprocess.run(
                ["uv", "run", "-m", "athena", "search", "--json", "café"],
                cwd=repo_root,
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            data = json.loads(result.stdout)
            assert len(data) == 1
            assert "café" in data[0]["summary"]

    def test_search_code_blocks_in_docstrings(self):
        """Test search with code examples in docstrings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".git").mkdir()
            test_file = repo_root / "test.py"
            test_file.write_text(
                '''def example():
    """
    Example function with code:

    ```python
    result = example()
    ```
    """
    return 1
'''
            )

            result = subprocess.run(
                ["uv", "run", "-m", "athena", "search", "--json", "example"],
                cwd=repo_root,
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            data = json.loads(result.stdout)
            assert len(data) == 1

    def test_search_very_long_query(self):
        """Test search with multi-sentence query."""
        query = "find all functions that parse Python code and extract docstrings from them"
        result = subprocess.run(
            ["uv", "run", "-m", "athena", "search", "--json", query],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        data = json.loads(result.stdout)
        # Should handle long queries gracefully
        assert isinstance(data, list)

    def test_search_special_characters_in_query(self):
        """Test search with special characters."""
        result = subprocess.run(
            ["uv", "run", "-m", "athena", "search", "--json", "parse() -> dict"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        data = json.loads(result.stdout)
        # Should handle special chars without crashing
        assert isinstance(data, list)

    def test_search_numbers_in_identifiers(self):
        """Test search with numbers in code identifiers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".git").mkdir()
            test_file = repo_root / "test.py"
            test_file.write_text(
                '''def handle_v2_auth():
    """Handle version 2 authentication."""
    return 1
'''
            )

            result = subprocess.run(
                ["uv", "run", "-m", "athena", "search", "--json", "version 2 authentication"],
                cwd=repo_root,
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            data = json.loads(result.stdout)
            assert len(data) == 1

    def test_search_no_repository_error(self):
        """Test search outside git repository."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Don't create .git directory
            result = subprocess.run(
                ["uv", "run", "-m", "athena", "search", "test"],
                cwd=tmpdir,
                capture_output=True,
                text=True
            )

            assert result.returncode == 1
            assert "Error:" in result.stderr

    def test_search_with_custom_config(self):
        """Test search uses .athena config if present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".git").mkdir()
            test_file = repo_root / "test.py"
            test_file.write_text(
                '''def foo():
    """First function."""
    return 1

def bar():
    """Second function."""
    return 2

def baz():
    """Third function."""
    return 3
'''
            )

            # Create config with max_results=2
            config_file = repo_root / ".athena"
            config_file.write_text(
                """search:
  term_frequency_saturation: 1.5
  length_normalization: 0.75
  max_results: 2
"""
            )

            result = subprocess.run(
                ["uv", "run", "-m", "athena", "search", "--json", "function"],
                cwd=repo_root,
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            data = json.loads(result.stdout)
            # Should respect config max_results
            assert len(data) <= 2

    def test_search_multiline_summary_in_table(self):
        """Test that table output wraps multiline summaries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".git").mkdir()
            test_file = repo_root / "test.py"
            test_file.write_text(
                '''def foo():
    """First line.

    Second line.
    Third line.
    """
    return 1
'''
            )

            result = subprocess.run(
                ["uv", "run", "-m", "athena", "search", "line"],
                cwd=repo_root,
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            # Table should show all lines of the summary (wrapped)
            assert "First line" in result.stdout
            assert "Second line" in result.stdout
            assert "Third line" in result.stdout

    def test_search_long_summary_in_table(self):
        """Test that table output wraps long single-line summaries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".git").mkdir()
            test_file = repo_root / "test.py"
            # Create a summary longer than 80 characters
            long_summary = "This is a very long summary that exceeds eighty characters and should be wrapped in the table output instead of being truncated"
            test_file.write_text(
                f'''def bar():
    """{long_summary}"""
    return 2
'''
            )

            result = subprocess.run(
                ["uv", "run", "-m", "athena", "search", "long summary"],
                cwd=repo_root,
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            # Table should show full summary (wrapped, not truncated)
            assert "This is a very long summary" in result.stdout
            assert "instead of being truncated" in result.stdout
            # Should not have ellipsis truncation
            assert "..." not in result.stdout or "..." in long_summary
