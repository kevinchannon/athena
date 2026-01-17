"""Tests for status module."""

import tempfile
from pathlib import Path

import pytest

from athena.status import check_status, check_status_recursive, filter_out_of_sync
from athena.models import EntityStatus, Location


class TestCheckStatus:
    """Tests for check_status function."""

    def test_check_status_function_without_hash(self):
        """Test checking status of function with no @athena tag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """def foo():
    return 1
"""
            )

            statuses = check_status("test.py:foo", repo_root)

            assert len(statuses) == 1
            assert statuses[0].kind == "function"
            assert statuses[0].path == "test.py:foo"
            assert statuses[0].recorded_hash is None
            assert len(statuses[0].calculated_hash) == 12

    def test_check_status_function_with_hash(self):
        """Test checking status of function with existing @athena tag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                '''def foo():
    """Docstring.
    @athena: abc123def456
    """
    return 1
'''
            )

            statuses = check_status("test.py:foo", repo_root)

            assert len(statuses) == 1
            assert statuses[0].recorded_hash == "abc123def456"
            assert statuses[0].calculated_hash != "abc123def456"

    def test_check_status_class(self):
        """Test checking status of class."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """class MyClass:
    pass
"""
            )

            statuses = check_status("test.py:MyClass", repo_root)

            assert len(statuses) == 1
            assert statuses[0].kind == "class"
            assert statuses[0].path == "test.py:MyClass"

    def test_check_status_nonexistent_entity_raises_error(self):
        """Test that checking nonexistent entity raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """def foo():
    pass
"""
            )

            with pytest.raises(ValueError, match="Entity not found"):
                check_status("test.py:bar", repo_root)


class TestCheckStatusRecursive:
    """Tests for check_status_recursive function."""

    def test_check_status_recursive_module(self):
        """Test recursive status check of a module."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """def foo():
    return 1

def bar():
    return 2

class MyClass:
    def method(self):
        return 3
"""
            )

            statuses = check_status_recursive("test.py", repo_root)

            # Should find 3 entities: foo, bar, MyClass (class), MyClass.method
            assert len(statuses) == 4
            paths = [s.path for s in statuses]
            assert "test.py:foo" in paths
            assert "test.py:bar" in paths
            assert "test.py:MyClass" in paths
            assert "test.py:MyClass.method" in paths

    def test_check_status_recursive_class(self):
        """Test recursive status check of a class."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """class MyClass:
    def method1(self):
        return 1

    def method2(self):
        return 2
"""
            )

            statuses = check_status_recursive("test.py:MyClass", repo_root)

            # Should find 3 entities: MyClass, method1, method2
            assert len(statuses) == 3
            paths = [s.path for s in statuses]
            assert "test.py:MyClass" in paths
            assert "test.py:MyClass.method1" in paths
            assert "test.py:MyClass.method2" in paths

    def test_check_status_recursive_function(self):
        """Test recursive status check of a function (no sub-entities)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """def foo():
    return 1
"""
            )

            statuses = check_status_recursive("test.py:foo", repo_root)

            # Should find only the function itself
            assert len(statuses) == 1
            assert statuses[0].path == "test.py:foo"


class TestFilterOutOfSync:
    """Tests for filter_out_of_sync function."""

    def test_filter_out_of_sync_with_no_hash(self):
        """Test filtering entities with no recorded hash."""
        statuses = [
            EntityStatus(
                kind="function",
                path="test.py:foo",
                extent=Location(start=0, end=1),
                recorded_hash=None,
                calculated_hash="abc123def456"
            ),
            EntityStatus(
                kind="function",
                path="test.py:bar",
                extent=Location(start=3, end=4),
                recorded_hash="abc123def456",
                calculated_hash="abc123def456"
            )
        ]

        out_of_sync = filter_out_of_sync(statuses)

        assert len(out_of_sync) == 1
        assert out_of_sync[0].path == "test.py:foo"

    def test_filter_out_of_sync_with_mismatched_hash(self):
        """Test filtering entities with mismatched hashes."""
        statuses = [
            EntityStatus(
                kind="function",
                path="test.py:foo",
                extent=Location(start=0, end=1),
                recorded_hash="oldoldoldold",
                calculated_hash="newnewnewnew"
            ),
            EntityStatus(
                kind="function",
                path="test.py:bar",
                extent=Location(start=3, end=4),
                recorded_hash="abc123def456",
                calculated_hash="abc123def456"
            )
        ]

        out_of_sync = filter_out_of_sync(statuses)

        assert len(out_of_sync) == 1
        assert out_of_sync[0].path == "test.py:foo"

    def test_filter_out_of_sync_all_in_sync(self):
        """Test filtering when all entities are in sync."""
        statuses = [
            EntityStatus(
                kind="function",
                path="test.py:foo",
                extent=Location(start=0, end=1),
                recorded_hash="abc123def456",
                calculated_hash="abc123def456"
            ),
            EntityStatus(
                kind="function",
                path="test.py:bar",
                extent=Location(start=3, end=4),
                recorded_hash="xyz789xyz789",
                calculated_hash="xyz789xyz789"
            )
        ]

        out_of_sync = filter_out_of_sync(statuses)

        assert len(out_of_sync) == 0

    def test_filter_out_of_sync_all_out_of_sync(self):
        """Test filtering when all entities are out of sync."""
        statuses = [
            EntityStatus(
                kind="function",
                path="test.py:foo",
                extent=Location(start=0, end=1),
                recorded_hash=None,
                calculated_hash="abc123def456"
            ),
            EntityStatus(
                kind="function",
                path="test.py:bar",
                extent=Location(start=3, end=4),
                recorded_hash="oldoldoldold",
                calculated_hash="newnewnewnew"
            )
        ]

        out_of_sync = filter_out_of_sync(statuses)

        assert len(out_of_sync) == 2
