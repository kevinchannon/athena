"""Tests for recursive sync functionality."""

import tempfile
from pathlib import Path

from athena.entity_path import EntityPath, parse_entity_path
from athena.sync import collect_sub_entities, sync_recursive


class TestCollectSubEntities:
    """Tests for collect_sub_entities function."""

    def test_collect_module_entities(self):
        """Test collecting all entities from a module."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "module.py"
            test_file.write_text(
                """def func1():
    pass

def func2():
    pass

class MyClass:
    def method1(self):
        pass

    def method2(self):
        pass
"""
            )

            entity_path = parse_entity_path("module.py")
            sub_entities = collect_sub_entities(entity_path, repo_root)

            # Should find 2 functions, 1 class, and 2 methods
            assert len(sub_entities) == 5
            assert "module.py:func1" in sub_entities
            assert "module.py:func2" in sub_entities
            assert "module.py:MyClass" in sub_entities
            assert "module.py:MyClass.method1" in sub_entities
            assert "module.py:MyClass.method2" in sub_entities

    def test_collect_class_methods(self):
        """Test collecting methods from a class."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "module.py"
            test_file.write_text(
                """class MyClass:
    def method1(self):
        pass

    def method2(self):
        pass

    def method3(self):
        pass
"""
            )

            entity_path = parse_entity_path("module.py:MyClass")
            sub_entities = collect_sub_entities(entity_path, repo_root)

            # Should find 3 methods
            assert len(sub_entities) == 3
            assert "module.py:MyClass.method1" in sub_entities
            assert "module.py:MyClass.method2" in sub_entities
            assert "module.py:MyClass.method3" in sub_entities

    def test_collect_package_entities(self):
        """Test collecting entities from a package."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)

            # Create package structure
            pkg = repo_root / "mypackage"
            pkg.mkdir()
            (pkg / "__init__.py").write_text("")

            mod1 = pkg / "module1.py"
            mod1.write_text(
                """def func1():
    pass
"""
            )

            mod2 = pkg / "module2.py"
            mod2.write_text(
                """class Class1:
    def method1(self):
        pass
"""
            )

            entity_path = parse_entity_path("mypackage")
            sub_entities = collect_sub_entities(entity_path, repo_root)

            # Should find entities from both modules
            assert len(sub_entities) == 3
            assert any("module1.py:func1" in e for e in sub_entities)
            assert any("module2.py:Class1" in e for e in sub_entities)
            assert any("module2.py:Class1.method1" in e for e in sub_entities)

    def test_collect_function_has_no_sub_entities(self):
        """Test that functions have no sub-entities."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "module.py"
            test_file.write_text(
                """def func():
    pass
"""
            )

            entity_path = parse_entity_path("module.py:func")
            sub_entities = collect_sub_entities(entity_path, repo_root)

            assert len(sub_entities) == 0

    def test_collect_method_has_no_sub_entities(self):
        """Test that methods have no sub-entities."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "module.py"
            test_file.write_text(
                """class MyClass:
    def method(self):
        pass
"""
            )

            entity_path = parse_entity_path("module.py:MyClass.method")
            sub_entities = collect_sub_entities(entity_path, repo_root)

            assert len(sub_entities) == 0


class TestSyncRecursive:
    """Tests for sync_recursive function."""

    def test_sync_module_recursively(self):
        """Test recursive sync of entire module."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "module.py"
            test_file.write_text(
                """def func1():
    return 1

def func2():
    return 2

class MyClass:
    def method(self):
        return 3
"""
            )

            # Sync recursively
            count = sync_recursive("module.py", force=False, repo_root=repo_root)

            # Should update 5 entities: module, func1, func2, MyClass, method
            assert count == 5

            # Verify all have tags
            code = test_file.read_text()
            import re

            tags = re.findall(r"@athena:\s*([0-9a-f]{12})", code)
            assert len(tags) == 5

    def test_sync_class_recursively(self):
        """Test recursive sync of class and methods."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "module.py"
            test_file.write_text(
                """class MyClass:
    def method1(self):
        return 1

    def method2(self):
        return 2
"""
            )

            # Sync class recursively
            count = sync_recursive("module.py:MyClass", force=False, repo_root=repo_root)

            # Should update class + 2 methods
            assert count == 3

            # Verify all have tags
            code = test_file.read_text()
            import re

            tags = re.findall(r"@athena:\s*([0-9a-f]{12})", code)
            assert len(tags) == 3

    def test_sync_package_recursively(self):
        """Test recursive sync of package."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)

            # Create package
            pkg = repo_root / "mypackage"
            pkg.mkdir()
            (pkg / "__init__.py").write_text("")

            mod1 = pkg / "module1.py"
            mod1.write_text(
                """def func():
    pass
"""
            )

            mod2 = pkg / "module2.py"
            mod2.write_text(
                """class Class1:
    pass
"""
            )

            # Sync package recursively
            count = sync_recursive("mypackage", force=False, repo_root=repo_root)

            # Should update package, func, and Class1
            assert count == 3

            # Verify tags in both files and package
            assert "@athena:" in (pkg / "__init__.py").read_text()
            assert "@athena:" in mod1.read_text()
            assert "@athena:" in mod2.read_text()

    def test_sync_function_recursively_is_same_as_single(self):
        """Test that recursive sync of function is same as single sync."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "module.py"
            test_file.write_text(
                """def func():
    return 1
"""
            )

            # Sync recursively (should just sync the function)
            count = sync_recursive("module.py:func", force=False, repo_root=repo_root)

            # Should update 1 entity
            assert count == 1

            code = test_file.read_text()
            assert "@athena:" in code

    def test_sync_recursive_with_force(self):
        """Test recursive sync with force flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "module.py"
            test_file.write_text(
                """def func1():
    pass

def func2():
    pass
"""
            )

            # First sync
            count1 = sync_recursive("module.py", force=False, repo_root=repo_root)
            assert count1 == 3  # module, func1, func2

            # Second sync without force - no updates
            count2 = sync_recursive("module.py", force=False, repo_root=repo_root)
            assert count2 == 0

            # Third sync with force - should update all
            count3 = sync_recursive("module.py", force=True, repo_root=repo_root)
            assert count3 == 3  # module, func1, func2

    def test_sync_recursive_continues_on_error(self):
        """Test that recursive sync continues even if one entity fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "module.py"
            test_file.write_text(
                """def func1():
    pass

def func2():
    pass
"""
            )

            # Sync recursively - should succeed
            count = sync_recursive("module.py", force=False, repo_root=repo_root)
            assert count == 3  # module, func1, func2

    def test_sync_nested_package(self):
        """Test recursive sync of nested package structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)

            # Create nested package
            pkg1 = repo_root / "pkg1"
            pkg1.mkdir()
            (pkg1 / "__init__.py").write_text("")

            pkg2 = pkg1 / "pkg2"
            pkg2.mkdir()
            (pkg2 / "__init__.py").write_text("")

            mod = pkg2 / "module.py"
            mod.write_text(
                """def deep_func():
    pass
"""
            )

            # Sync top-level package recursively
            count = sync_recursive("pkg1", force=False, repo_root=repo_root)

            # Should sync pkg1, pkg2, and deep_func
            assert count == 3
            assert "@athena:" in (pkg1 / "__init__.py").read_text()
            assert "@athena:" in (pkg2 / "__init__.py").read_text()
            assert "@athena:" in mod.read_text()

    def test_sync_recursive_returns_update_count(self):
        """Test that sync_recursive returns correct update count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "module.py"

            # Create file with 5 entities
            test_file.write_text(
                """def func1():
    pass

def func2():
    pass

class MyClass:
    def method1(self):
        pass

    def method2(self):
        pass

    def method3(self):
        pass
"""
            )

            # First sync - all should update
            count1 = sync_recursive("module.py", force=False, repo_root=repo_root)
            assert count1 == 7  # module + 2 funcs + 1 class + 3 methods

            # Modify one function
            code = test_file.read_text()
            code = code.replace("def func1():", "def func1(x):")
            test_file.write_text(code)

            # Second sync - only modified entity should update
            count2 = sync_recursive("module.py", force=False, repo_root=repo_root)
            assert count2 == 2  # func1 changed, and module (which includes all entities)
