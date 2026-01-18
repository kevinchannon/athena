"""End-to-end tests for package entity support."""

import subprocess
import tempfile
from pathlib import Path


def run_sync(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Helper to run sync command via subprocess."""
    return subprocess.run(
        ["uv", "run", "-m", "athena", "sync"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def run_info(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Helper to run info command via subprocess."""
    return subprocess.run(
        ["uv", "run", "-m", "athena", "info"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def run_status(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Helper to run status command via subprocess."""
    return subprocess.run(
        ["uv", "run", "-m", "athena", "status"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
    )


class TestPackageSyncE2E:
    """End-to-end tests for package entity support."""

    def test_package_sync_end_to_end(self):
        """Test full package sync workflow from creation to verification."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / ".git").mkdir()

            # Create package structure
            pkg = tmp_path / "mypackage"
            pkg.mkdir()
            init_file = pkg / "__init__.py"
            init_file.write_text('"""My package for testing."""\n\n')

            # Create module
            (pkg / "module.py").write_text(
                """def helper():
    return 42
"""
            )

            # Sync package
            result = run_sync(["mypackage", "--recursive"], tmp_path)
            assert result.returncode == 0

            # Verify package __init__.py has tag
            init_code = init_file.read_text()
            assert "@athena:" in init_code

            # Verify module has tag
            module_code = (pkg / "module.py").read_text()
            assert "@athena:" in module_code

            # Verify idempotency - second sync should report no updates
            result2 = run_sync(["mypackage", "--recursive"], tmp_path)
            assert result2.returncode == 0
            assert "No updates needed" in result2.stdout

    def test_nested_packages_sync_independently(self):
        """Test that nested packages sync independently."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / ".git").mkdir()

            # Create parent package
            parent = tmp_path / "parent"
            parent.mkdir()
            (parent / "__init__.py").write_text('"""Parent package."""\n\n')

            # Create child package
            child = parent / "child"
            child.mkdir()
            (child / "__init__.py").write_text('"""Child package."""\n\n')

            # Create module in child
            (child / "module.py").write_text("def func():\n    pass\n")

            # Sync both packages
            result = run_sync(["parent", "--recursive"], tmp_path)
            assert result.returncode == 0

            # Verify both have tags
            parent_code = (parent / "__init__.py").read_text()
            assert "@athena:" in parent_code
            import re

            parent_hash = re.search(r"@athena:\s*([0-9a-f]{12})", parent_code).group(1)

            child_code = (child / "__init__.py").read_text()
            assert "@athena:" in child_code
            child_hash = re.search(r"@athena:\s*([0-9a-f]{12})", child_code).group(1)

            # Modify child module content
            (child / "module.py").write_text("def func():\n    return 42\n")

            # Sync again
            run_sync(["parent", "--recursive"], tmp_path)

            # Parent hash should NOT change (child content change doesn't affect parent)
            parent_code_after = (parent / "__init__.py").read_text()
            parent_hash_after = re.search(
                r"@athena:\s*([0-9a-f]{12})", parent_code_after
            ).group(1)
            assert parent_hash == parent_hash_after

            # Child hash SHOULD change (its module content changed)
            child_code_after = (child / "__init__.py").read_text()
            child_hash_after = re.search(
                r"@athena:\s*([0-9a-f]{12})", child_code_after
            ).group(1)
            # Actually, child hash should NOT change because package hash is based on
            # manifest (what files exist), not their content
            assert child_hash == child_hash_after

    def test_package_structural_changes_update_hash(self):
        """Test that package hash changes when structure changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / ".git").mkdir()

            # Create package
            pkg = tmp_path / "pkg"
            pkg.mkdir()
            init_file = pkg / "__init__.py"
            init_file.write_text('"""Package."""\n\n')

            # Initial sync
            run_sync(["pkg", "--recursive"], tmp_path)

            init_code = init_file.read_text()
            import re

            hash_v1 = re.search(r"@athena:\s*([0-9a-f]{12})", init_code).group(1)

            # Add a new file (structural change)
            (pkg / "newmodule.py").write_text("def new():\n    pass\n")

            # Sync again
            run_sync(["pkg", "--recursive"], tmp_path)

            init_code_v2 = init_file.read_text()
            hash_v2 = re.search(r"@athena:\s*([0-9a-f]{12})", init_code_v2).group(1)

            # Hash should change
            assert hash_v1 != hash_v2

    def test_package_content_changes_dont_update_hash(self):
        """Test that package hash is stable when only module content changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / ".git").mkdir()

            # Create package with module
            pkg = tmp_path / "pkg"
            pkg.mkdir()
            init_file = pkg / "__init__.py"
            init_file.write_text('"""Package."""\n\n')

            module = pkg / "module.py"
            module.write_text("def func():\n    return 1\n")

            # Initial sync
            run_sync(["pkg", "--recursive"], tmp_path)

            init_code = init_file.read_text()
            import re

            hash_v1 = re.search(r"@athena:\s*([0-9a-f]{12})", init_code).group(1)

            # Modify module content (not structure)
            module.write_text("def func():\n    return 2\n")

            # Sync again
            run_sync(["pkg", "--recursive"], tmp_path)

            init_code_v2 = init_file.read_text()
            hash_v2 = re.search(r"@athena:\s*([0-9a-f]{12})", init_code_v2).group(1)

            # Hash should NOT change
            assert hash_v1 == hash_v2

    def test_namespace_package_not_treated_as_entity(self):
        """Test that namespace packages (dirs without __init__.py) are not treated as package entities."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / ".git").mkdir()

            # Create namespace package (no __init__.py)
            namespace_pkg = tmp_path / "namespace"
            namespace_pkg.mkdir()

            # Create module in namespace package
            module = namespace_pkg / "module.py"
            module.write_text("def func():\n    pass\n")

            # Sync should work for the module
            result = run_sync(["namespace/module.py", "--recursive"], tmp_path)
            assert result.returncode == 0

            # Module should have tag
            module_code = module.read_text()
            assert "@athena:" in module_code

            # But there should be no __init__.py created
            assert not (namespace_pkg / "__init__.py").exists()

    def test_package_info_command_works(self):
        """Test that athena info works on packages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / ".git").mkdir()

            # Create package
            pkg = tmp_path / "pkg"
            pkg.mkdir()
            (pkg / "__init__.py").write_text('"""Test package."""\n\n')

            # Sync package
            run_sync(["pkg"], tmp_path)

            # Run info
            result = run_info(["pkg"], tmp_path)

            # Should succeed and show package info
            assert result.returncode == 0
            assert "pkg" in result.stdout

    def test_package_status_command_works(self):
        """Test that athena status works on packages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / ".git").mkdir()

            # Create package
            pkg = tmp_path / "pkg"
            pkg.mkdir()
            init_file = pkg / "__init__.py"
            init_file.write_text('"""Test package."""\n\n')

            # Sync package
            run_sync(["pkg"], tmp_path)

            # Run status
            result = run_status(["pkg"], tmp_path)

            # Should succeed and show status
            assert result.returncode == 0
            # After sync, should show "in sync"
            assert "pkg" in result.stdout

            # Add a file (structural change)
            (pkg / "new.py").write_text("def new():\n    pass\n")

            # Run status again
            result2 = run_status(["pkg"], tmp_path)
            assert result2.returncode == 0
            # Should detect the change
            assert "pkg" in result2.stdout
