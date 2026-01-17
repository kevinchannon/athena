"""End-to-end tests for status command."""

import subprocess
import tempfile
from pathlib import Path

import pytest


class TestStatusE2E:
    """End-to-end tests for status command via CLI."""

    def test_status_single_function_out_of_sync(self):
        """Test status command on single function without hash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """def foo():
    return 1
"""
            )

            result = subprocess.run(
                ["uv", "run", "-m", "athena", "status", "test.py:foo"],
                cwd=repo_root,
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            assert "1 entities need updating" in result.stdout
            assert "function" in result.stdout
            assert "test.py:foo" in result.stdout
            assert "<NONE>" in result.stdout

    def test_status_single_function_in_sync(self):
        """Test status command on function with correct hash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """def foo():
    return 1
"""
            )

            # First sync it
            subprocess.run(
                ["uv", "run", "-m", "athena", "sync", "test.py:foo"],
                cwd=repo_root,
                capture_output=True
            )

            # Now check status
            result = subprocess.run(
                ["uv", "run", "-m", "athena", "status", "test.py:foo"],
                cwd=repo_root,
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            assert "All entities are in sync" in result.stdout

    def test_status_recursive_module(self):
        """Test status command with --recursive on module."""
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

            result = subprocess.run(
                ["uv", "run", "-m", "athena", "status", "test.py", "--recursive"],
                cwd=repo_root,
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            assert "4 entities need updating" in result.stdout
            assert "test.py:foo" in result.stdout
            assert "test.py:bar" in result.stdout
            assert "test.py:MyClass" in result.stdout
            assert "test.py:MyClass.method" in result.stdout

    def test_status_recursive_class(self):
        """Test status command with -r on class."""
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

            result = subprocess.run(
                ["uv", "run", "-m", "athena", "status", "test.py:MyClass", "-r"],
                cwd=repo_root,
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            assert "3 entities need updating" in result.stdout
            assert "test.py:MyClass" in result.stdout
            assert "test.py:MyClass.method1" in result.stdout
            assert "test.py:MyClass.method2" in result.stdout

    def test_status_default_entire_project(self):
        """Test status command with no entity (entire project)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)

            # Create multiple files
            file1 = repo_root / "test1.py"
            file1.write_text(
                """def foo():
    return 1
"""
            )

            file2 = repo_root / "test2.py"
            file2.write_text(
                """def bar():
    return 2
"""
            )

            result = subprocess.run(
                ["uv", "run", "-m", "athena", "status"],
                cwd=repo_root,
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            assert "entities need updating" in result.stdout
            assert "test1.py:foo" in result.stdout
            assert "test2.py:bar" in result.stdout

    def test_status_nonexistent_entity_error(self):
        """Test status command with nonexistent entity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """def foo():
    pass
"""
            )

            result = subprocess.run(
                ["uv", "run", "-m", "athena", "status", "test.py:bar"],
                cwd=repo_root,
                capture_output=True,
                text=True
            )

            assert result.returncode == 1
            assert "Error:" in result.stderr
            assert "not found" in result.stderr

    def test_status_nonexistent_file_error(self):
        """Test status command with nonexistent file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)

            result = subprocess.run(
                ["uv", "run", "-m", "athena", "status", "nonexistent.py:foo"],
                cwd=repo_root,
                capture_output=True,
                text=True
            )

            assert result.returncode == 1
            assert "Error:" in result.stderr

    def test_status_out_of_sync_after_code_change(self):
        """Test that status detects out-of-sync after code change."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"

            # Create and sync initial version
            test_file.write_text(
                """def foo():
    return 1
"""
            )
            subprocess.run(
                ["uv", "run", "-m", "athena", "sync", "test.py:foo"],
                cwd=repo_root,
                capture_output=True
            )

            # Modify the code
            test_file.write_text(
                """def foo():
    return 2
"""
            )

            # Check status
            result = subprocess.run(
                ["uv", "run", "-m", "athena", "status", "test.py:foo"],
                cwd=repo_root,
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            assert "1 entities need updating" in result.stdout
            # Should show both hashes are different
            assert "test.py:foo" in result.stdout

    def test_status_mixed_sync_states(self):
        """Test status with mix of synced and unsynced entities."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """def foo():
    return 1

def bar():
    return 2
"""
            )

            # Sync only foo
            subprocess.run(
                ["uv", "run", "-m", "athena", "sync", "test.py:foo"],
                cwd=repo_root,
                capture_output=True
            )

            # Check status recursively
            result = subprocess.run(
                ["uv", "run", "-m", "athena", "status", "test.py", "-r"],
                cwd=repo_root,
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            # Only bar should be out of sync
            assert "1 entities need updating" in result.stdout
            assert "test.py:bar" in result.stdout
            # foo should not appear (it's in sync)
            lines = result.stdout.split("\n")
            # Count occurrences - should only appear once in the table
            foo_count = sum(1 for line in lines if "test.py:foo" in line)
            assert foo_count == 0  # foo is in sync, should not be in output
