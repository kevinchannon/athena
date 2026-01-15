"""End-to-end tests for sync functionality on realistic code."""

from pathlib import Path

from typer.testing import CliRunner

from athena.cli import app

runner = CliRunner()


class TestSyncE2E:
    """End-to-end tests running sync on realistic code."""

    def test_sync_real_python_module(self):
        """Test syncing a realistic Python module with multiple entities."""
        with runner.isolated_filesystem():
            Path(".git").mkdir()

            # Create a realistic module
            module = Path("calculator.py")
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

            # Run sync
            result = runner.invoke(app, ["sync", "calculator.py", "--recursive"])

            # Should succeed
            assert result.exit_code > 0  # Positive exit code = number of updates
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
        with runner.isolated_filesystem():
            Path(".git").mkdir()

            # Create package structure
            pkg = Path("mathlib")
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
            result = runner.invoke(app, ["sync", "mathlib", "--recursive"])

            # Should succeed
            assert result.exit_code > 0

            # Verify tags in arithmetic module
            arith_code = arithmetic.read_text()
            assert "@athena:" in arith_code

            # Verify tags in geometry module
            geom_code = geometry.read_text()
            assert "@athena:" in geom_code

    def test_sync_idempotency(self):
        """Test that syncing twice produces same result."""
        with runner.isolated_filesystem():
            Path(".git").mkdir()

            module = Path("test.py")
            module.write_text(
                """def func():
    return 42
"""
            )

            # First sync
            result1 = runner.invoke(app, ["sync", "test.py:func"])
            assert result1.exit_code == 1  # 1 update

            code_after_first = module.read_text()

            # Second sync - should report no updates
            result2 = runner.invoke(app, ["sync", "test.py:func"])
            assert result2.exit_code == 0  # No updates
            assert "No updates needed" in result2.stdout

            code_after_second = module.read_text()

            # Code should be identical
            assert code_after_first == code_after_second

    def test_sync_detects_code_changes(self):
        """Test that sync detects when code changes."""
        with runner.isolated_filesystem():
            Path(".git").mkdir()

            module = Path("test.py")

            # Initial version
            module.write_text(
                """def compute(x):
    return x * 2
"""
            )

            # First sync
            runner.invoke(app, ["sync", "test.py:compute"])

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
            runner.invoke(app, ["sync", "test.py:compute"])

            code_v2 = module.read_text()
            hash_v2 = re.search(r"@athena:\s*([0-9a-f]{12})", code_v2).group(1)

            # Hashes should be different
            assert hash_v1 != hash_v2

    def test_sync_with_existing_docstrings(self):
        """Test that sync preserves existing docstring content."""
        with runner.isolated_filesystem():
            Path(".git").mkdir()

            module = Path("test.py")
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
            runner.invoke(app, ["sync", "test.py:important_function"])

            # Verify original content preserved
            updated_code = module.read_text()
            assert "very important function" in updated_code
            assert "critical operations" in updated_code
            assert "Args:" in updated_code
            assert "Returns:" in updated_code
            assert "@athena:" in updated_code

    def test_sync_force_flag(self):
        """Test that --force flag forces recalculation."""
        with runner.isolated_filesystem():
            Path(".git").mkdir()

            module = Path("test.py")
            module.write_text(
                """def func():
    return 1
"""
            )

            # Initial sync
            runner.invoke(app, ["sync", "test.py:func"])

            # Sync without changes - should report no updates
            result1 = runner.invoke(app, ["sync", "test.py:func"])
            assert result1.exit_code == 0
            assert "No updates needed" in result1.stdout

            # Sync with --force - should update
            result2 = runner.invoke(app, ["sync", "test.py:func", "--force"])
            assert result2.exit_code == 1
            assert "Updated" in result2.stdout

    def test_sync_entire_project(self):
        """Test syncing entire project without specifying entity."""
        with runner.isolated_filesystem():
            Path(".git").mkdir()

            # Create multiple files
            Path("file1.py").write_text("def func1():\n    pass\n")
            Path("file2.py").write_text("def func2():\n    pass\n")
            Path("file3.py").write_text("class MyClass:\n    pass\n")

            # Sync entire project (no entity specified)
            result = runner.invoke(app, ["sync"])

            # Should sync all entities
            assert result.exit_code > 0  # Updated count

            # Verify all files have tags
            assert "@athena:" in Path("file1.py").read_text()
            assert "@athena:" in Path("file2.py").read_text()
            assert "@athena:" in Path("file3.py").read_text()

    def test_sync_error_handling(self):
        """Test that sync handles errors gracefully."""
        with runner.isolated_filesystem():
            Path(".git").mkdir()

            # Try to sync non-existent file
            result = runner.invoke(app, ["sync", "nonexistent.py:func"])

            # Should fail with non-zero exit code
            assert result.exit_code != 0
            assert "Error" in result.stdout or "Error" in result.stderr
