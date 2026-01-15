"""End-to-end tests for sync functionality on realistic code."""

import subprocess
import tempfile
from pathlib import Path


class TestSyncE2E:
    """End-to-end tests running sync via subprocess on realistic code."""

    def test_sync_real_python_module(self):
        """Test syncing a realistic Python module with multiple entities."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".git").mkdir()

            # Create a realistic module
            module = repo_root / "calculator.py"
            module.write_text(
                '''"""Calculator module for basic math operations."""


class Calculator:
    """A simple calculator class."""

    def __init__(self):
        self.result = 0

    def add(self, x: int, y: int) -> int:
        """Add two numbers."""
        return x + y

    def subtract(self, x: int, y: int) -> int:
        """Subtract y from x."""
        return x - y

    def multiply(self, x: int, y: int) -> int:
        """Multiply two numbers."""
        return x * y

    def divide(self, x: float, y: float) -> float:
        """Divide x by y."""
        if y == 0:
            raise ValueError("Cannot divide by zero")
        return x / y


def create_calculator() -> Calculator:
    """Factory function to create a calculator."""
    return Calculator()
'''
            )

            # Run sync via subprocess
            result = subprocess.run(
                ["python", "-m", "athena", "sync", "calculator.py", "--recursive"],
                cwd=repo_root,
                capture_output=True,
                text=True,
            )

            # Should succeed
            assert result.returncode > 0  # Positive exit code = number of updates
            assert "Synced" in result.stdout

            # Verify tags were added
            updated_code = module.read_text()
            import re

            tags = re.findall(r"@athena:\s*([0-9a-f]{12})", updated_code)
            # Should have tags for: Calculator class + 5 methods (__init__, add, subtract, multiply, divide) + 1 function = 7 tags
            assert len(tags) == 7

            # Verify tags are valid hex
            for tag in tags:
                assert len(tag) == 12
                assert all(c in "0123456789abcdef" for c in tag)

    def test_sync_package_structure(self):
        """Test syncing a package with multiple modules."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".git").mkdir()

            # Create package structure
            pkg = repo_root / "mathlib"
            pkg.mkdir()
            (pkg / "__init__.py").write_text('"""Math library package."""')

            # Create arithmetic module
            arithmetic = pkg / "arithmetic.py"
            arithmetic.write_text(
                """def add(a, b):
    return a + b


def subtract(a, b):
    return a - b
"""
            )

            # Create geometry module
            geometry = pkg / "geometry.py"
            geometry.write_text(
                """import math


class Circle:
    def __init__(self, radius):
        self.radius = radius

    def area(self):
        return math.pi * self.radius ** 2

    def circumference(self):
        return 2 * math.pi * self.radius
"""
            )

            # Sync entire package
            result = subprocess.run(
                ["python", "-m", "athena", "sync", "mathlib", "--recursive"],
                cwd=repo_root,
                capture_output=True,
                text=True,
            )

            # Should succeed
            assert result.returncode > 0

            # Verify tags in arithmetic module
            arith_code = arithmetic.read_text()
            assert "@athena:" in arith_code

            # Verify tags in geometry module
            geom_code = geometry.read_text()
            assert "@athena:" in geom_code

    def test_sync_idempotency(self):
        """Test that syncing twice produces same result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".git").mkdir()

            module = repo_root / "test.py"
            module.write_text(
                """def func():
    return 42
"""
            )

            # First sync
            result1 = subprocess.run(
                ["python", "-m", "athena", "sync", "test.py:func"],
                cwd=repo_root,
                capture_output=True,
                text=True,
            )
            assert result1.returncode == 1  # 1 update

            code_after_first = module.read_text()

            # Second sync - should report no updates
            result2 = subprocess.run(
                ["python", "-m", "athena", "sync", "test.py:func"],
                cwd=repo_root,
                capture_output=True,
                text=True,
            )
            assert result2.returncode == 0  # No updates
            assert "No updates needed" in result2.stdout

            code_after_second = module.read_text()

            # Code should be identical
            assert code_after_first == code_after_second

    def test_sync_detects_code_changes(self):
        """Test that sync detects when code changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".git").mkdir()

            module = repo_root / "test.py"

            # Initial version
            module.write_text(
                """def compute(x):
    return x * 2
"""
            )

            # First sync
            subprocess.run(
                ["python", "-m", "athena", "sync", "test.py:compute"],
                cwd=repo_root,
                capture_output=True,
                text=True,
            )

            code_v1 = module.read_text()
            import re

            hash_v1 = re.search(r"@athena:\s*([0-9a-f]{12})", code_v1).group(1)

            # Modify code
            module.write_text(
                """def compute(x):
    return x * 3
"""
            )

            # Second sync
            subprocess.run(
                ["python", "-m", "athena", "sync", "test.py:compute"],
                cwd=repo_root,
                capture_output=True,
                text=True,
            )

            code_v2 = module.read_text()
            hash_v2 = re.search(r"@athena:\s*([0-9a-f]{12})", code_v2).group(1)

            # Hashes should be different
            assert hash_v1 != hash_v2

    def test_sync_with_existing_docstrings(self):
        """Test that sync preserves existing docstring content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".git").mkdir()

            module = repo_root / "test.py"
            module.write_text(
                '''def important_function(x, y):
    """This is a very important function.

    It does critical operations and should not be modified.
    The documentation is comprehensive and valuable.

    Args:
        x: First parameter
        y: Second parameter

    Returns:
        The result of the operation
    """
    return x + y
'''
            )

            # Sync
            subprocess.run(
                ["python", "-m", "athena", "sync", "test.py:important_function"],
                cwd=repo_root,
                capture_output=True,
                text=True,
            )

            # Verify original content preserved
            updated_code = module.read_text()
            assert "very important function" in updated_code
            assert "critical operations" in updated_code
            assert "Args:" in updated_code
            assert "Returns:" in updated_code
            assert "@athena:" in updated_code

    def test_sync_force_flag(self):
        """Test that --force flag forces recalculation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".git").mkdir()

            module = repo_root / "test.py"
            module.write_text(
                """def func():
    return 1
"""
            )

            # Initial sync
            subprocess.run(
                ["python", "-m", "athena", "sync", "test.py:func"],
                cwd=repo_root,
                capture_output=True,
                text=True,
            )

            # Sync without changes - should report no updates
            result1 = subprocess.run(
                ["python", "-m", "athena", "sync", "test.py:func"],
                cwd=repo_root,
                capture_output=True,
                text=True,
            )
            assert result1.returncode == 0
            assert "No updates needed" in result1.stdout

            # Sync with --force - should update
            result2 = subprocess.run(
                ["python", "-m", "athena", "sync", "test.py:func", "--force"],
                cwd=repo_root,
                capture_output=True,
                text=True,
            )
            assert result2.returncode == 1
            assert "Updated" in result2.stdout

    def test_sync_entire_project(self):
        """Test syncing entire project without specifying entity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".git").mkdir()

            # Create multiple files
            (repo_root / "file1.py").write_text("def func1():\n    pass\n")
            (repo_root / "file2.py").write_text("def func2():\n    pass\n")
            (repo_root / "file3.py").write_text("class MyClass:\n    pass\n")

            # Sync entire project (no entity specified)
            result = subprocess.run(
                ["python", "-m", "athena", "sync"],
                cwd=repo_root,
                capture_output=True,
                text=True,
            )

            # Should sync all entities
            assert result.returncode > 0  # Updated count

            # Verify all files have tags
            assert "@athena:" in (repo_root / "file1.py").read_text()
            assert "@athena:" in (repo_root / "file2.py").read_text()
            assert "@athena:" in (repo_root / "file3.py").read_text()

    def test_sync_error_handling(self):
        """Test that sync handles errors gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".git").mkdir()

            # Try to sync non-existent file
            result = subprocess.run(
                ["python", "-m", "athena", "sync", "nonexistent.py:func"],
                cwd=repo_root,
                capture_output=True,
                text=True,
            )

            # Should fail with non-zero exit code
            assert result.returncode != 0
            assert "Error" in result.stdout or "Error" in result.stderr
