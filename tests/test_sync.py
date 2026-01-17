"""Tests for sync module - core sync logic."""

import tempfile
from pathlib import Path

import pytest

from athena.sync import inspect_entity, needs_update, sync_entity


class TestNeedsUpdate:
    """Tests for needs_update function."""

    def test_needs_update_when_no_current_hash(self):
        """Test that update is needed when no current hash exists."""
        assert needs_update(None, "abc123def456", force=False) is True

    def test_needs_update_when_hashes_differ(self):
        """Test that update is needed when hashes don't match."""
        assert needs_update("oldoldoldold", "newnewnewnew", force=False) is True

    def test_no_update_needed_when_hashes_match(self):
        """Test that update is not needed when hashes match."""
        assert needs_update("abc123def456", "abc123def456", force=False) is False

    def test_force_always_updates(self):
        """Test that force flag always triggers update."""
        # Even with matching hashes
        assert needs_update("abc123def456", "abc123def456", force=True) is True

        # With no current hash
        assert needs_update(None, "abc123def456", force=True) is True

        # With different hashes
        assert needs_update("oldoldoldold", "newnewnewnew", force=True) is True


class TestSyncEntity:
    """Tests for sync_entity function."""

    def test_sync_function_without_docstring(self):
        """Test syncing function that has no docstring."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """def foo():
    return 1
"""
            )

            # Sync the function
            result = sync_entity("test.py:foo", force=False, repo_root=repo_root)

            # Should have updated (inserted new docstring)
            assert result is True

            # Check that docstring was added
            updated_code = test_file.read_text()
            assert "@athena:" in updated_code
            assert '"""' in updated_code

    def test_sync_function_with_existing_tag(self):
        """Test syncing function with existing @athena tag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            original_code = '''def foo():
    """Docstring.
    @athena: oldoldoldold
    """
    return 1
'''
            test_file.write_text(original_code)

            # Sync the function
            result = sync_entity("test.py:foo", force=False, repo_root=repo_root)

            # Should have updated
            assert result is True

            # Check that tag was updated
            updated_code = test_file.read_text()
            assert "@athena:" in updated_code
            assert "oldoldoldold" not in updated_code
            # New hash should be present (we don't know exact value)
            assert updated_code != original_code

    def test_sync_function_no_update_when_hash_matches(self):
        """Test that function is not updated when hash already matches."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"

            # First, create function and sync it to get correct hash
            initial_code = """def foo():
    return 1
"""
            test_file.write_text(initial_code)
            sync_entity("test.py:foo", force=False, repo_root=repo_root)

            # Read the synced code
            synced_code = test_file.read_text()

            # Write it back (simulating no changes)
            test_file.write_text(synced_code)

            # Sync again - should return False (no update)
            result = sync_entity("test.py:foo", force=False, repo_root=repo_root)
            assert result is False

            # Code should be unchanged
            assert test_file.read_text() == synced_code

    def test_sync_function_with_force_flag(self):
        """Test that force flag updates even when hash matches."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"

            # Create and sync function
            test_file.write_text(
                """def foo():
    return 1
"""
            )
            sync_entity("test.py:foo", force=False, repo_root=repo_root)
            synced_code = test_file.read_text()

            # Sync again with force=True
            result = sync_entity("test.py:foo", force=True, repo_root=repo_root)

            # Should return True even though hash matches
            assert result is True

            # Code should be the same (hash regenerated to same value)
            assert test_file.read_text() == synced_code

    def test_sync_class(self):
        """Test syncing a class."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """class MyClass:
    def method(self):
        pass
"""
            )

            # Sync the class
            result = sync_entity("test.py:MyClass", force=False, repo_root=repo_root)

            # Should have updated
            assert result is True

            # Check that docstring was added to class
            updated_code = test_file.read_text()
            assert "@athena:" in updated_code

    def test_sync_method(self):
        """Test syncing a method within a class."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """class MyClass:
    def my_method(self):
        return 42
"""
            )

            # Sync the method
            result = sync_entity(
                "test.py:MyClass.my_method", force=False, repo_root=repo_root
            )

            # Should have updated
            assert result is True

            # Check that docstring was added to method
            updated_code = test_file.read_text()
            assert "@athena:" in updated_code

    def test_sync_decorated_function(self):
        """Test syncing decorated function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """@decorator
def foo():
    return 1
"""
            )

            # Sync the function
            result = sync_entity("test.py:foo", force=False, repo_root=repo_root)

            # Should have updated
            assert result is True

            # Check that docstring was added
            updated_code = test_file.read_text()
            assert "@athena:" in updated_code
            # Decorator should still be present
            assert "@decorator" in updated_code

    def test_sync_function_hash_changes_with_code_change(self):
        """Test that hash changes when code changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"

            # Create and sync initial version
            test_file.write_text(
                """def foo():
    return 1
"""
            )
            sync_entity("test.py:foo", force=False, repo_root=repo_root)
            first_sync = test_file.read_text()

            # Modify the function
            test_file.write_text(
                """def foo():
    return 2
"""
            )

            # Sync again
            result = sync_entity("test.py:foo", force=False, repo_root=repo_root)

            # Should have updated (hash changed)
            assert result is True

            second_sync = test_file.read_text()

            # Code should be different (different hash)
            # Extract hashes from both versions
            import re

            hash1 = re.search(r"@athena:\s*([0-9a-f]{12})", first_sync).group(1)
            hash2 = re.search(r"@athena:\s*([0-9a-f]{12})", second_sync).group(1)

            assert hash1 != hash2

    def test_sync_nonexistent_file_raises_error(self):
        """Test that syncing nonexistent file raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)

            with pytest.raises(FileNotFoundError):
                sync_entity("nonexistent.py:foo", force=False, repo_root=repo_root)

    def test_sync_nonexistent_entity_raises_error(self):
        """Test that syncing nonexistent entity raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """def foo():
    pass
"""
            )

            with pytest.raises(ValueError, match="Entity not found"):
                sync_entity("test.py:bar", force=False, repo_root=repo_root)

    def test_sync_invalid_path_raises_error(self):
        """Test that invalid path raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)

            with pytest.raises(ValueError):
                sync_entity("", force=False, repo_root=repo_root)

    def test_sync_module_level_not_implemented(self):
        """Test that module-level sync raises NotImplementedError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text('"""Module docstring."""\n')

            with pytest.raises(NotImplementedError, match="Module-level"):
                sync_entity("test.py", force=False, repo_root=repo_root)

    def test_sync_package_level_not_implemented(self):
        """Test that package-level sync raises NotImplementedError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            package_dir = repo_root / "mypackage"
            package_dir.mkdir()
            (package_dir / "__init__.py").write_text("")

            with pytest.raises(NotImplementedError, match="Package-level"):
                sync_entity("mypackage", force=False, repo_root=repo_root)

    def test_sync_preserves_existing_docstring_content(self):
        """Test that sync preserves existing docstring content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                '''def foo():
    """This is my important docstring.

    It has multiple lines and details.
    """
    return 1
'''
            )

            # Sync the function
            sync_entity("test.py:foo", force=False, repo_root=repo_root)

            # Check that original content is preserved
            updated_code = test_file.read_text()
            assert "important docstring" in updated_code
            assert "multiple lines" in updated_code
            assert "@athena:" in updated_code

    def test_sync_excludes_athena_package(self):
        """Test that sync does not modify files under athena package."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)

            # Create a fake athena package structure
            athena_dir = repo_root / "src" / "athena"
            athena_dir.mkdir(parents=True)

            cli_file = athena_dir / "cli.py"
            cli_file.write_text(
                """def some_function():
    return 42
"""
            )

            # Create .git to mark as repo root
            (repo_root / ".git").mkdir()

            # Try to sync the athena package - should raise ValueError
            with pytest.raises(ValueError, match="Cannot inspect excluded path"):
                sync_entity("src/athena/cli.py:some_function", force=False, repo_root=repo_root)


class TestInspectEntity:
    """Tests for inspect_entity function."""

    def test_inspect_function_without_hash(self):
        """Test inspecting function that has no @athena tag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """def foo():
    return 1
"""
            )

            status = inspect_entity("test.py:foo", repo_root)

            assert status.kind == "function"
            assert status.path == "test.py:foo"
            assert status.extent == "0-1"
            assert status.recorded_hash is None
            assert len(status.calculated_hash) == 12

    def test_inspect_function_with_hash(self):
        """Test inspecting function with existing @athena tag."""
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

            status = inspect_entity("test.py:foo", repo_root)

            assert status.kind == "function"
            assert status.recorded_hash == "abc123def456"
            assert status.calculated_hash != "abc123def456"

    def test_inspect_class(self):
        """Test inspecting class."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """class MyClass:
    pass
"""
            )

            status = inspect_entity("test.py:MyClass", repo_root)

            assert status.kind == "class"
            assert status.path == "test.py:MyClass"
            assert len(status.calculated_hash) == 12

    def test_inspect_method(self):
        """Test inspecting class method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """class MyClass:
    def my_method(self):
        return 42
"""
            )

            status = inspect_entity("test.py:MyClass.my_method", repo_root)

            assert status.kind == "method"
            assert status.path == "test.py:MyClass.my_method"
            assert len(status.calculated_hash) == 12

    def test_inspect_decorated_function(self):
        """Test inspecting decorated function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """@decorator
def foo():
    return 1
"""
            )

            status = inspect_entity("test.py:foo", repo_root)

            assert status.kind == "function"
            # Extent should include decorator
            assert status.extent.startswith("0-")

    def test_inspect_nonexistent_file_raises_error(self):
        """Test that inspecting nonexistent file raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)

            with pytest.raises(FileNotFoundError):
                inspect_entity("nonexistent.py:foo", repo_root)

    def test_inspect_nonexistent_entity_raises_error(self):
        """Test that inspecting nonexistent entity raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """def foo():
    pass
"""
            )

            with pytest.raises(ValueError, match="Entity not found"):
                inspect_entity("test.py:bar", repo_root)
