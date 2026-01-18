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

    def test_sync_module_without_docstring(self):
        """Test syncing module that has no docstring."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text("x = 1\n")

            # Sync the module
            result = sync_entity("test.py", force=False, repo_root=repo_root)

            # Should have updated (inserted new docstring)
            assert result is True

            # Check that docstring was added
            updated_code = test_file.read_text()
            assert "@athena:" in updated_code
            assert '"""' in updated_code

    def test_sync_module_with_existing_tag(self):
        """Test syncing module with existing @athena tag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            original_code = '"""Module docstring.\n@athena: oldoldoldold\n"""\nx = 1\n'
            test_file.write_text(original_code)

            # Sync the module
            result = sync_entity("test.py", force=False, repo_root=repo_root)

            # Should have updated
            assert result is True

            # Check that tag was updated
            updated_code = test_file.read_text()
            assert "@athena:" in updated_code
            assert "oldoldoldold" not in updated_code
            # New hash should be present
            assert updated_code != original_code

    def test_sync_module_no_update_when_hash_matches(self):
        """Test that module is not updated when hash already matches."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"

            # First, create module and sync it to get correct hash
            initial_code = "x = 1\n"
            test_file.write_text(initial_code)
            sync_entity("test.py", force=False, repo_root=repo_root)

            # Read the synced code
            synced_code = test_file.read_text()

            # Write it back (simulating no changes)
            test_file.write_text(synced_code)

            # Sync again - should return False (no update)
            result = sync_entity("test.py", force=False, repo_root=repo_root)
            assert result is False

            # Code should be unchanged
            assert test_file.read_text() == synced_code

    def test_sync_module_with_shebang(self):
        """Test syncing module with shebang line."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text("#!/usr/bin/env python3\nx = 1\n")

            # Sync the module
            result = sync_entity("test.py", force=False, repo_root=repo_root)

            # Should have updated
            assert result is True

            # Check that shebang is preserved
            updated_code = test_file.read_text()
            lines = updated_code.splitlines()
            assert lines[0] == "#!/usr/bin/env python3"
            assert "@athena:" in updated_code

    def test_sync_module_with_encoding_declaration(self):
        """Test syncing module with encoding declaration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text("# -*- coding: utf-8 -*-\nx = 1\n")

            # Sync the module
            result = sync_entity("test.py", force=False, repo_root=repo_root)

            # Should have updated
            assert result is True

            # Check that encoding is preserved
            updated_code = test_file.read_text()
            lines = updated_code.splitlines()
            assert lines[0] == "# -*- coding: utf-8 -*-"
            assert "@athena:" in updated_code

    def test_sync_module_with_both_headers(self):
        """Test syncing module with both shebang and encoding."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                "#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\nx = 1\n"
            )

            # Sync the module
            result = sync_entity("test.py", force=False, repo_root=repo_root)

            # Should have updated
            assert result is True

            # Check that both headers are preserved
            updated_code = test_file.read_text()
            lines = updated_code.splitlines()
            assert lines[0] == "#!/usr/bin/env python3"
            assert lines[1] == "# -*- coding: utf-8 -*-"
            assert "@athena:" in updated_code

    def test_sync_empty_module(self):
        """Test syncing an empty module."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text("")

            # Sync the module
            result = sync_entity("test.py", force=False, repo_root=repo_root)

            # Should have updated
            assert result is True

            # Check that docstring was added
            updated_code = test_file.read_text()
            assert "@athena:" in updated_code
            assert '"""' in updated_code

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
            assert status.extent.start == 0
            assert status.extent.end == 1
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
            assert status.extent.start == 0

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

    def test_inspect_module_no_docstring(self):
        """Test inspecting module without docstring."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text("x = 1\ny = 2\n")

            status = inspect_entity("test.py", repo_root)

            assert status.kind == "module"
            assert status.path == "test.py"
            assert status.extent.start == 0
            assert status.extent.end == 1  # Last line (0-indexed)
            assert status.recorded_hash is None
            assert len(status.calculated_hash) == 12

    def test_inspect_module_with_docstring_no_tag(self):
        """Test inspecting module with docstring but no @athena tag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text('"""Module docstring."""\nx = 1\n')

            status = inspect_entity("test.py", repo_root)

            assert status.kind == "module"
            assert status.recorded_hash is None
            assert len(status.calculated_hash) == 12

    def test_inspect_module_with_tag(self):
        """Test inspecting module with existing @athena tag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                '"""Module docstring.\n@athena: abc123def456\n"""\nx = 1\n'
            )

            status = inspect_entity("test.py", repo_root)

            assert status.kind == "module"
            assert status.recorded_hash == "abc123def456"
            assert len(status.calculated_hash) == 12
            # Hash should not match the arbitrary one we put in
            assert status.calculated_hash != "abc123def456"

    def test_inspect_module_hash_matches(self):
        """Test inspecting module where computed hash matches recorded hash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"

            # First write code and compute its hash
            from athena.hashing import compute_module_hash
            code = "x = 1\ny = 2\n"
            computed_hash = compute_module_hash(code)

            # Now write file with that hash in docstring
            test_file.write_text(
                f'"""Module.\n@athena: {computed_hash}\n"""\n{code}'
            )

            status = inspect_entity("test.py", repo_root)

            assert status.kind == "module"
            assert status.recorded_hash == computed_hash
            assert status.calculated_hash == computed_hash

    def test_inspect_module_hash_mismatch(self):
        """Test inspecting module where hashes don't match."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                '"""Module.\n@athena: abcdef012345\n"""\nx = 1\n'
            )

            status = inspect_entity("test.py", repo_root)

            assert status.kind == "module"
            assert status.recorded_hash == "abcdef012345"
            assert status.calculated_hash != "abcdef012345"


class TestInspectPackage:
    """Tests for package entity inspection."""

    def test_inspect_package_empty_init(self):
        """Test inspecting package with empty __init__.py."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            package_dir = repo_root / "mypackage"
            package_dir.mkdir()
            init_file = package_dir / "__init__.py"
            init_file.write_text("")

            status = inspect_entity("mypackage", repo_root)

            assert status.kind == "package"
            assert status.path == "mypackage"
            assert status.extent.start == 0
            assert status.extent.end == 0  # Dummy extent for packages
            assert status.recorded_hash is None
            assert len(status.calculated_hash) == 12

    def test_inspect_package_with_init_code(self):
        """Test inspecting package with code in __init__.py."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            package_dir = repo_root / "mypackage"
            package_dir.mkdir()
            init_file = package_dir / "__init__.py"
            init_file.write_text("from .module import foo\n")

            status = inspect_entity("mypackage", repo_root)

            assert status.kind == "package"
            assert status.path == "mypackage"
            assert status.recorded_hash is None
            assert len(status.calculated_hash) == 12

    def test_inspect_package_with_docstring_no_tag(self):
        """Test inspecting package with docstring but no @athena tag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            package_dir = repo_root / "mypackage"
            package_dir.mkdir()
            init_file = package_dir / "__init__.py"
            init_file.write_text('"""Package docstring."""\n')

            status = inspect_entity("mypackage", repo_root)

            assert status.kind == "package"
            assert status.recorded_hash is None
            assert len(status.calculated_hash) == 12

    def test_inspect_package_with_tag(self):
        """Test inspecting package with existing @athena tag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            package_dir = repo_root / "mypackage"
            package_dir.mkdir()
            init_file = package_dir / "__init__.py"
            init_file.write_text(
                '"""Package docstring.\n@athena: abc123def456\n"""\n'
            )

            status = inspect_entity("mypackage", repo_root)

            assert status.kind == "package"
            assert status.recorded_hash == "abc123def456"
            assert len(status.calculated_hash) == 12
            # Hash should not match the arbitrary one we put in
            assert status.calculated_hash != "abc123def456"

    def test_inspect_package_hash_reflects_structure(self):
        """Test that package hash reflects its file structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            package_dir = repo_root / "mypackage"
            package_dir.mkdir()
            init_file = package_dir / "__init__.py"
            init_file.write_text("")

            # Inspect empty package
            status1 = inspect_entity("mypackage", repo_root)
            hash1 = status1.calculated_hash

            # Add a module file
            module_file = package_dir / "module.py"
            module_file.write_text("def foo(): pass\n")

            # Inspect again
            status2 = inspect_entity("mypackage", repo_root)
            hash2 = status2.calculated_hash

            # Hash should have changed
            assert hash1 != hash2

            # Add a sub-package
            subpkg_dir = package_dir / "subpkg"
            subpkg_dir.mkdir()
            subpkg_init = subpkg_dir / "__init__.py"
            subpkg_init.write_text("")

            # Inspect again
            status3 = inspect_entity("mypackage", repo_root)
            hash3 = status3.calculated_hash

            # Hash should have changed again
            assert hash2 != hash3


class TestSyncPackage:
    """Tests for package entity sync."""

    def test_sync_package_empty_init(self):
        """Test syncing package with empty __init__.py."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            package_dir = repo_root / "mypackage"
            package_dir.mkdir()
            init_file = package_dir / "__init__.py"
            init_file.write_text("")

            # Sync the package
            result = sync_entity("mypackage", force=False, repo_root=repo_root)

            # Should have updated (inserted new docstring)
            assert result is True

            # Check that docstring was added to __init__.py
            updated_code = init_file.read_text()
            assert "@athena:" in updated_code
            assert '"""' in updated_code

    def test_sync_package_with_existing_tag(self):
        """Test syncing package with existing @athena tag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            package_dir = repo_root / "mypackage"
            package_dir.mkdir()
            init_file = package_dir / "__init__.py"
            original_code = '"""Package docstring.\n@athena: oldoldoldold\n"""\n'
            init_file.write_text(original_code)

            # Sync the package
            result = sync_entity("mypackage", force=False, repo_root=repo_root)

            # Should have updated
            assert result is True

            # Check that tag was updated
            updated_code = init_file.read_text()
            assert "@athena:" in updated_code
            assert "oldoldoldold" not in updated_code
            # New hash should be present
            assert updated_code != original_code

    def test_sync_package_no_update_when_hash_matches(self):
        """Test that package is not updated when hash already matches."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            package_dir = repo_root / "mypackage"
            package_dir.mkdir()
            init_file = package_dir / "__init__.py"
            init_file.write_text("")

            # First, sync package to get correct hash
            sync_entity("mypackage", force=False, repo_root=repo_root)

            # Read the synced code
            synced_code = init_file.read_text()

            # Write it back (simulating no changes)
            init_file.write_text(synced_code)

            # Sync again - should return False (no update)
            result = sync_entity("mypackage", force=False, repo_root=repo_root)
            assert result is False

            # Code should be unchanged
            assert init_file.read_text() == synced_code

    def test_sync_package_creates_init_if_missing(self):
        """Test syncing package creates __init__.py if missing (namespace → package conversion)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            package_dir = repo_root / "mypackage"
            package_dir.mkdir()

            # Note: No __init__.py file created initially
            # This represents a namespace package

            # Try to sync the package
            # Note: This should work because sync logic handles missing __init__.py
            result = sync_entity("mypackage", force=False, repo_root=repo_root)

            # Should have updated (created new file with docstring)
            assert result is True

            # Check that __init__.py was created with docstring
            init_file = package_dir / "__init__.py"
            assert init_file.exists()
            updated_code = init_file.read_text()
            assert "@athena:" in updated_code
            assert '"""' in updated_code

    def test_sync_package_with_shebang_in_init(self):
        """Test syncing package with shebang line in __init__.py."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            package_dir = repo_root / "mypackage"
            package_dir.mkdir()
            init_file = package_dir / "__init__.py"
            init_file.write_text("#!/usr/bin/env python3\n")

            # Sync the package
            result = sync_entity("mypackage", force=False, repo_root=repo_root)

            # Should have updated
            assert result is True

            # Check that shebang is preserved
            updated_code = init_file.read_text()
            lines = updated_code.splitlines()
            assert lines[0] == "#!/usr/bin/env python3"
            assert "@athena:" in updated_code

    def test_sync_package_with_encoding_in_init(self):
        """Test syncing package with encoding declaration in __init__.py."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            package_dir = repo_root / "mypackage"
            package_dir.mkdir()
            init_file = package_dir / "__init__.py"
            init_file.write_text("# -*- coding: utf-8 -*-\n")

            # Sync the package
            result = sync_entity("mypackage", force=False, repo_root=repo_root)

            # Should have updated
            assert result is True

            # Check that encoding is preserved
            updated_code = init_file.read_text()
            lines = updated_code.splitlines()
            assert lines[0] == "# -*- coding: utf-8 -*-"
            assert "@athena:" in updated_code


class TestMultiLineSignatures:
    """Tests for correct handling of multi-line signatures and class definitions."""

    def test_sync_function_with_multiline_signature(self):
        """Test that sync correctly handles functions with multi-line signatures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """def my_function(
    arg1: str,
    arg2: int
) -> str:
    return "hello"
"""
            )

            # Sync the function
            result = sync_entity("test.py:my_function", force=False, repo_root=repo_root)
            assert result is True

            # Read the updated code
            updated_code = test_file.read_text()
            lines = updated_code.splitlines()

            # Find the closing paren with colon
            colon_idx = None
            for i, line in enumerate(lines):
                if ") -> str:" in line:
                    colon_idx = i
                    break

            assert colon_idx is not None, "Could not find end of signature"

            # Docstring should be on the line AFTER the closing paren
            assert lines[colon_idx + 1].strip().startswith('"""'), \
                f"Expected docstring after line {colon_idx}, but found: {lines[colon_idx + 1]}"
            assert "@athena:" in updated_code

    def test_sync_function_with_multiline_signature_and_decorator(self):
        """Test multi-line signature with decorator."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """@decorator
def my_function(
    arg1: str,
    arg2: int
) -> str:
    return "hello"
"""
            )

            result = sync_entity("test.py:my_function", force=False, repo_root=repo_root)
            assert result is True

            updated_code = test_file.read_text()
            lines = updated_code.splitlines()

            # Find decorator, signature end, and docstring
            assert lines[0] == "@decorator"
            colon_idx = None
            for i, line in enumerate(lines):
                if ") -> str:" in line:
                    colon_idx = i
                    break

            assert colon_idx is not None
            assert lines[colon_idx + 1].strip().startswith('"""'), \
                f"Expected docstring after signature at line {colon_idx + 1}"

    def test_sync_class_with_multiline_bases(self):
        """Test class with multiple base classes on separate lines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """class MyClass(
    BaseClass1,
    BaseClass2,
    BaseClass3
):
    pass
"""
            )

            result = sync_entity("test.py:MyClass", force=False, repo_root=repo_root)
            assert result is True

            updated_code = test_file.read_text()
            lines = updated_code.splitlines()

            # Find the closing paren with colon
            colon_idx = None
            for i, line in enumerate(lines):
                if "):" in line and "BaseClass" not in line:
                    colon_idx = i
                    break

            assert colon_idx is not None
            assert lines[colon_idx + 1].strip().startswith('"""'), \
                f"Expected docstring after class definition at line {colon_idx + 1}"

    def test_sync_class_with_multiline_bases_and_decorator(self):
        """Test decorated class with multi-line base classes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """@dataclass
class MyClass(
    BaseClass1,
    BaseClass2
):
    x: int = 1
"""
            )

            result = sync_entity("test.py:MyClass", force=False, repo_root=repo_root)
            assert result is True

            updated_code = test_file.read_text()
            lines = updated_code.splitlines()

            assert lines[0] == "@dataclass"
            colon_idx = None
            for i, line in enumerate(lines):
                if "):" in line and "BaseClass" not in line:
                    colon_idx = i
                    break

            assert colon_idx is not None
            assert lines[colon_idx + 1].strip().startswith('"""')

    def test_sync_method_with_multiline_signature(self):
        """Test method with multi-line signature."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """class MyClass:
    def my_method(
        self,
        arg1: str,
        arg2: int
    ) -> str:
        return "hello"
"""
            )

            result = sync_entity("test.py:MyClass.my_method", force=False, repo_root=repo_root)
            assert result is True

            updated_code = test_file.read_text()
            lines = updated_code.splitlines()

            colon_idx = None
            for i, line in enumerate(lines):
                if ") -> str:" in line:
                    colon_idx = i
                    break

            assert colon_idx is not None
            assert lines[colon_idx + 1].strip().startswith('"""')

    def test_sync_function_with_complex_signature(self):
        """Test function with very complex multi-line signature."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """def complex_func(
    x: int,
    y: str = "default",
    *args,
    z: bool = False,
    **kwargs
) -> tuple[int, str]:
    return (x, y)
"""
            )

            result = sync_entity("test.py:complex_func", force=False, repo_root=repo_root)
            assert result is True

            updated_code = test_file.read_text()
            lines = updated_code.splitlines()

            colon_idx = None
            for i, line in enumerate(lines):
                if ") -> tuple[int, str]:" in line:
                    colon_idx = i
                    break

            assert colon_idx is not None
            assert lines[colon_idx + 1].strip().startswith('"""'), \
                f"Expected docstring after signature at line {colon_idx + 1}"
            # Verify signature is preserved
            assert "x: int" in updated_code
            assert "*args" in updated_code
            assert "**kwargs" in updated_code


class TestDecoratedClassMethods:
    """Tests for syncing methods within decorated classes."""

    def test_sync_method_in_decorated_class(self):
        """Test syncing a regular method in a decorated class."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """@decorator
class MyClass:
    def my_method(self):
        return "hello"
"""
            )

            # Sync the method
            result = sync_entity("test.py:MyClass.my_method", force=False, repo_root=repo_root)
            assert result is True

            updated_code = test_file.read_text()
            assert "@athena:" in updated_code
            # Decorator should still be present
            assert "@decorator" in updated_code

    def test_sync_post_init_in_dataclass(self):
        """Test syncing __post_init__ method in a dataclass."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """from dataclasses import dataclass

@dataclass
class Environment:
    name: str

    def __post_init__(self):
        pass
"""
            )

            # Sync the __post_init__ method
            result = sync_entity("test.py:Environment.__post_init__", force=False, repo_root=repo_root)
            assert result is True

            updated_code = test_file.read_text()
            assert "@athena:" in updated_code
            assert "@dataclass" in updated_code

    def test_inspect_method_in_decorated_class(self):
        """Test inspecting a method in a decorated class."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """@dataclass
class MyClass:
    x: int

    def process(self):
        return self.x * 2
"""
            )

            # Inspect should find the method
            status = inspect_entity("test.py:MyClass.process", repo_root)

            assert status is not None
            assert status.kind == "method"

    def test_sync_dunder_init_in_decorated_class(self):
        """Test syncing __init__ method in a decorated class."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """@decorator
class MyClass:
    def __init__(self, value):
        self.value = value
"""
            )

            result = sync_entity("test.py:MyClass.__init__", force=False, repo_root=repo_root)
            assert result is True

            updated_code = test_file.read_text()
            assert "@athena:" in updated_code


class TestDecoratorHandling:
    """Tests for correct handling of decorators in sync and status commands."""

    def test_sync_function_with_single_decorator(self):
        """Test that sync correctly handles functions with single decorator."""
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
            assert result is True

            # Read the updated code
            updated_code = test_file.read_text()
            lines = updated_code.splitlines()

            # Verify structure: decorator, then def, then docstring
            assert lines[0] == "@decorator"
            assert lines[1] == "def foo():"
            assert lines[2].strip().startswith('"""')
            assert "@athena:" in updated_code

            # Verify docstring is NOT between decorator and def
            assert "@decorator\n@athena:" not in updated_code
            assert '@decorator\n"""' not in updated_code

    def test_sync_function_with_multiple_decorators(self):
        """Test that sync correctly handles functions with multiple decorators."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """@decorator1
@decorator2
@decorator3
def bar():
    return 2
"""
            )

            # Sync the function
            result = sync_entity("test.py:bar", force=False, repo_root=repo_root)
            assert result is True

            # Read the updated code
            updated_code = test_file.read_text()
            lines = updated_code.splitlines()

            # Verify structure: decorators, then def, then docstring
            assert lines[0] == "@decorator1"
            assert lines[1] == "@decorator2"
            assert lines[2] == "@decorator3"
            assert lines[3] == "def bar():"
            assert lines[4].strip().startswith('"""')
            assert "@athena:" in updated_code

            # Verify no docstring between decorators
            for i in range(3):
                assert '"""' not in lines[i]

    def test_sync_class_with_decorator(self):
        """Test that sync correctly handles classes with decorators."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """@dataclass
class MyClass:
    x: int
"""
            )

            # Sync the class
            result = sync_entity("test.py:MyClass", force=False, repo_root=repo_root)
            assert result is True

            # Read the updated code
            updated_code = test_file.read_text()
            lines = updated_code.splitlines()

            # Verify structure: decorator, then class, then docstring
            assert lines[0] == "@dataclass"
            assert lines[1] == "class MyClass:"
            assert lines[2].strip().startswith('"""')
            assert "@athena:" in updated_code

            # Verify docstring is NOT between decorator and class
            assert "@dataclass\n@athena:" not in updated_code
            assert '@dataclass\n"""' not in updated_code

    def test_sync_method_with_decorator(self):
        """Test that sync correctly handles methods with decorators."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """class MyClass:
    @property
    def value(self):
        return self._value
"""
            )

            # Sync the method
            result = sync_entity("test.py:MyClass.value", force=False, repo_root=repo_root)
            assert result is True

            # Read the updated code
            updated_code = test_file.read_text()
            lines = updated_code.splitlines()

            # Find the decorator and method lines
            decorator_idx = None
            def_idx = None
            for i, line in enumerate(lines):
                if "@property" in line:
                    decorator_idx = i
                if "def value" in line:
                    def_idx = i

            assert decorator_idx is not None
            assert def_idx is not None

            # Verify decorator comes before def
            assert decorator_idx < def_idx

            # Verify docstring comes after def, not between decorator and def
            assert def_idx == decorator_idx + 1
            assert lines[def_idx + 1].strip().startswith('"""')
            assert "@athena:" in updated_code

    def test_inspect_identifies_decorated_function(self):
        """Test that inspect_entity correctly identifies decorated functions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """@decorator
def foo():
    return 1
"""
            )

            # Inspect should successfully identify the entity
            status = inspect_entity("test.py:foo", repo_root)

            assert status is not None
            assert status.kind == "function"
            # Extent should include the decorator
            assert status.extent.start == 0  # First line (decorator)
            assert status.extent.end == 2    # Last line (return statement)

    def test_inspect_identifies_decorated_class(self):
        """Test that inspect_entity correctly identifies decorated classes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """@dataclass
class MyClass:
    x: int
"""
            )

            # Inspect should successfully identify the entity
            status = inspect_entity("test.py:MyClass", repo_root)

            assert status is not None
            assert status.kind == "class"
            # Extent should include the decorator
            assert status.extent.start == 0  # First line (decorator)

    def test_inspect_identifies_decorated_method(self):
        """Test that inspect_entity correctly identifies decorated methods."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """class MyClass:
    @staticmethod
    def helper():
        return True
"""
            )

            # Inspect should successfully identify the entity
            status = inspect_entity("test.py:MyClass.helper", repo_root)

            assert status is not None
            assert status.kind == "method"
            # Extent should include the decorator (relative to class)
            assert status.extent.start == 1  # @staticmethod line

    def test_sync_decorated_function_preserves_decorator_arguments(self):
        """Test that decorators with arguments are preserved correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text(
                """@app.route('/users', methods=['GET', 'POST'])
def users():
    return []
"""
            )

            # Sync the function
            result = sync_entity("test.py:users", force=False, repo_root=repo_root)
            assert result is True

            # Read the updated code
            updated_code = test_file.read_text()
            lines = updated_code.splitlines()

            # Verify decorator with args is preserved
            assert "@app.route('/users', methods=['GET', 'POST'])" in lines[0]
            assert lines[1] == "def users():"
            assert lines[2].strip().startswith('"""')
            assert "@athena:" in updated_code
