"""Integration tests for sync functionality."""

import tempfile
from pathlib import Path

from athena.sync import sync_entity


class TestSyncIntegration:
    """Integration tests for sync operations."""

    def test_roundtrip_function_sync(self):
        """Test complete roundtrip: create, sync, modify, sync again."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "module.py"

            # Step 1: Create function
            test_file.write_text(
                """def calculate(x, y):
    return x + y
"""
            )

            # Step 2: Initial sync
            result1 = sync_entity("module.py:calculate", force=False, repo_root=repo_root)
            assert result1 is True  # Should update

            code_after_first_sync = test_file.read_text()
            assert "@athena:" in code_after_first_sync

            # Step 3: Sync again without changes - should not update
            result2 = sync_entity("module.py:calculate", force=False, repo_root=repo_root)
            assert result2 is False  # No update needed

            code_after_second_sync = test_file.read_text()
            assert code_after_second_sync == code_after_first_sync

            # Step 4: Modify function
            test_file.write_text(
                """def calculate(x, y):
    return x * y
"""
            )

            # Step 5: Sync after modification - hash should change
            result3 = sync_entity("module.py:calculate", force=False, repo_root=repo_root)
            assert result3 is True  # Should update

            code_after_third_sync = test_file.read_text()
            assert "@athena:" in code_after_third_sync

            # Extract and compare hashes
            import re

            hash1 = re.search(r"@athena:\s*([0-9a-f]{12})", code_after_first_sync).group(1)
            hash3 = re.search(r"@athena:\s*([0-9a-f]{12})", code_after_third_sync).group(1)
            assert hash1 != hash3  # Hashes should differ

    def test_sync_multiple_entities_in_file(self):
        """Test syncing multiple entities in the same file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "module.py"

            # Create file with multiple entities
            test_file.write_text(
                """def func1():
    return 1

def func2():
    return 2

class MyClass:
    def method(self):
        pass
"""
            )

            # Sync all entities
            result1 = sync_entity("module.py:func1", force=False, repo_root=repo_root)
            assert result1 is True

            result2 = sync_entity("module.py:func2", force=False, repo_root=repo_root)
            assert result2 is True

            result3 = sync_entity("module.py:MyClass", force=False, repo_root=repo_root)
            assert result3 is True

            result4 = sync_entity(
                "module.py:MyClass.method", force=False, repo_root=repo_root
            )
            assert result4 is True

            # Verify all entities have tags
            code = test_file.read_text()
            import re

            tags = re.findall(r"@athena:\s*([0-9a-f]{12})", code)
            assert len(tags) == 4  # Should have 4 tags

    def test_sync_nested_package_structure(self):
        """Test syncing entities in nested package structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)

            # Create nested structure
            pkg1 = repo_root / "pkg1"
            pkg1.mkdir()
            (pkg1 / "__init__.py").write_text("")

            pkg2 = pkg1 / "pkg2"
            pkg2.mkdir()
            (pkg2 / "__init__.py").write_text("")

            module = pkg2 / "module.py"
            module.write_text(
                """def deep_function():
    return "deep"
"""
            )

            # Sync the deeply nested function
            result = sync_entity(
                "pkg1/pkg2/module.py:deep_function", force=False, repo_root=repo_root
            )
            assert result is True

            # Verify tag added
            code = module.read_text()
            assert "@athena:" in code

    def test_sync_with_complex_function_signature(self):
        """Test syncing function with complex signature."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "module.py"

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

            result = sync_entity("module.py:complex_func", force=False, repo_root=repo_root)
            assert result is True

            code = test_file.read_text()
            assert "@athena:" in code

            # Verify signature is preserved
            assert "x: int" in code
            assert "*args" in code
            assert "**kwargs" in code

    def test_sync_preserves_decorators_and_formatting(self):
        """Test that sync preserves decorators and code formatting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "module.py"

            original_code = """@decorator1
@decorator2(arg="value")
def decorated_func():
    \"\"\"Original docstring.\"\"\"
    x = 1
    y = 2
    return x + y
"""
            test_file.write_text(original_code)

            sync_entity("module.py:decorated_func", force=False, repo_root=repo_root)

            updated_code = test_file.read_text()

            # Verify decorators preserved
            assert "@decorator1" in updated_code
            assert '@decorator2(arg="value")' in updated_code

            # Verify formatting preserved
            assert "x = 1" in updated_code
            assert "y = 2" in updated_code

            # Verify tag added
            assert "@athena:" in updated_code

    def test_sync_class_with_multiple_methods(self):
        """Test syncing class and its methods."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "module.py"

            test_file.write_text(
                """class Calculator:
    def add(self, x, y):
        return x + y

    def subtract(self, x, y):
        return x - y

    def multiply(self, x, y):
        return x * y
"""
            )

            # Sync the class
            result_class = sync_entity(
                "module.py:Calculator", force=False, repo_root=repo_root
            )
            assert result_class is True

            # Sync each method
            result_add = sync_entity(
                "module.py:Calculator.add", force=False, repo_root=repo_root
            )
            assert result_add is True

            result_sub = sync_entity(
                "module.py:Calculator.subtract", force=False, repo_root=repo_root
            )
            assert result_sub is True

            result_mul = sync_entity(
                "module.py:Calculator.multiply", force=False, repo_root=repo_root
            )
            assert result_mul is True

            # Verify all have tags
            code = test_file.read_text()
            import re

            tags = re.findall(r"@athena:\s*([0-9a-f]{12})", code)
            assert len(tags) == 4  # Class + 3 methods

    def test_hash_stability_across_whitespace_changes(self):
        """Test that hash remains stable across whitespace-only changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "module.py"

            # Create function with specific formatting
            test_file.write_text(
                """def foo():
    return 1
"""
            )

            # First sync
            sync_entity("module.py:foo", force=False, repo_root=repo_root)
            code1 = test_file.read_text()

            # Extract hash
            import re

            hash1 = re.search(r"@athena:\s*([0-9a-f]{12})", code1).group(1)

            # Modify with extra whitespace (but same AST)
            test_file.write_text(
                """def foo():


    return 1
"""
            )

            # Sync again
            sync_entity("module.py:foo", force=False, repo_root=repo_root)
            code2 = test_file.read_text()

            hash2 = re.search(r"@athena:\s*([0-9a-f]{12})", code2).group(1)

            # Hashes should be the same (AST unchanged)
            assert hash1 == hash2
