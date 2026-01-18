"""Tests for entity path parsing and resolution."""

import tempfile
from pathlib import Path

import pytest

from athena.entity_path import EntityPath, parse_entity_path, resolve_entity_path


class TestEntityPath:
    """Tests for EntityPath dataclass properties."""

    def test_is_package(self):
        """Test package detection."""
        path = EntityPath(file_path="src/athena", entity_name=None)
        assert path.is_package is True
        assert path.is_module is False

    def test_is_module(self):
        """Test module detection."""
        path = EntityPath(file_path="src/athena/cli.py", entity_name=None)
        assert path.is_module is True
        assert path.is_package is False

    def test_is_class(self):
        """Test class detection."""
        path = EntityPath(file_path="models.py", entity_name="Entity")
        assert path.is_class is True
        assert path.is_method is False

    def test_is_method(self):
        """Test method detection."""
        path = EntityPath(file_path="parser.py", entity_name="Parser.parse")
        assert path.is_method is True
        assert path.is_class is False

    def test_class_name_extraction(self):
        """Test extracting class name from method path."""
        path = EntityPath(file_path="foo.py", entity_name="MyClass.my_method")
        assert path.class_name == "MyClass"

    def test_class_name_none_for_non_method(self):
        """Test class_name is None for non-method paths."""
        path = EntityPath(file_path="foo.py", entity_name="function")
        assert path.class_name is None

    def test_method_name_extraction(self):
        """Test extracting method name from method path."""
        path = EntityPath(file_path="foo.py", entity_name="MyClass.my_method")
        assert path.method_name == "my_method"

    def test_method_name_none_for_non_method(self):
        """Test method_name is None for non-method paths."""
        path = EntityPath(file_path="foo.py", entity_name="function")
        assert path.method_name is None


class TestParseEntityPath:
    """Tests for parse_entity_path function."""

    def test_parse_full_path_with_method(self):
        """Test parsing full path with class and method."""
        result = parse_entity_path("src/foo/bar.py:Baz.bax")
        assert result.file_path == "src/foo/bar.py"
        assert result.entity_name == "Baz.bax"
        assert result.is_method is True

    def test_parse_module_with_class(self):
        """Test parsing module with class only."""
        result = parse_entity_path("models.py:Entity")
        assert result.file_path == "models.py"
        assert result.entity_name == "Entity"
        assert result.is_class is True

    def test_parse_module_with_function(self):
        """Test parsing module with function."""
        result = parse_entity_path("utils.py:helper_func")
        assert result.file_path == "utils.py"
        assert result.entity_name == "helper_func"

    def test_parse_module_only(self):
        """Test parsing module without entity."""
        result = parse_entity_path("src/athena/cli.py")
        assert result.file_path == "src/athena/cli.py"
        assert result.entity_name is None
        assert result.is_module is True

    def test_parse_package_path(self):
        """Test parsing package directory."""
        result = parse_entity_path("src/athena")
        assert result.file_path == "src/athena"
        assert result.entity_name is None
        assert result.is_package is True

    def test_parse_relative_path(self):
        """Test parsing relative path."""
        result = parse_entity_path("models.py")
        assert result.file_path == "models.py"
        assert result.entity_name is None

    def test_parse_nested_path(self):
        """Test parsing deeply nested path."""
        result = parse_entity_path("a/b/c/d/file.py:Class.method")
        assert result.file_path == "a/b/c/d/file.py"
        assert result.entity_name == "Class.method"

    def test_parse_empty_path_raises_error(self):
        """Test that empty path raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_entity_path("")

    def test_parse_whitespace_only_raises_error(self):
        """Test that whitespace-only path raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_entity_path("   ")

    def test_parse_empty_entity_after_colon(self):
        """Test parsing with colon but no entity name."""
        result = parse_entity_path("file.py:")
        assert result.file_path == "file.py"
        assert result.entity_name is None

    def test_parse_strips_whitespace(self):
        """Test that whitespace is stripped from components."""
        result = parse_entity_path("  file.py  :  Entity  ")
        assert result.file_path == "file.py"
        assert result.entity_name == "Entity"

    def test_parse_file_path_only_with_colon_raises_error(self):
        """Test that colon without file path raises error."""
        with pytest.raises(ValueError, match="File path component cannot be empty"):
            parse_entity_path(":Entity")

    def test_parse_complex_entity_path(self):
        """Test parsing complex nested entity."""
        # Note: Current implementation only supports one level of nesting (Class.method)
        result = parse_entity_path("file.py:OuterClass.InnerClass")
        assert result.file_path == "file.py"
        assert result.entity_name == "OuterClass.InnerClass"


class TestResolveEntityPath:
    """Tests for resolve_entity_path function."""

    def test_resolve_existing_file(self):
        """Test resolving path to existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text("# test file")

            entity_path = EntityPath(file_path="test.py", entity_name=None)
            result = resolve_entity_path(entity_path, repo_root)

            assert result is not None
            assert result.exists()
            assert result == test_file

    def test_resolve_existing_file_with_entity(self):
        """Test resolving path with entity specification."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text("class Foo: pass")

            entity_path = EntityPath(file_path="test.py", entity_name="Foo")
            result = resolve_entity_path(entity_path, repo_root)

            assert result is not None
            assert result == test_file

    def test_resolve_nested_file(self):
        """Test resolving nested file path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            nested_dir = repo_root / "a" / "b" / "c"
            nested_dir.mkdir(parents=True)
            test_file = nested_dir / "test.py"
            test_file.write_text("# nested")

            entity_path = EntityPath(file_path="a/b/c/test.py", entity_name=None)
            result = resolve_entity_path(entity_path, repo_root)

            assert result is not None
            assert result.exists()
            assert result == test_file

    def test_resolve_package_with_init(self):
        """Test resolving package directory with __init__.py."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            package_dir = repo_root / "mypackage"
            package_dir.mkdir()
            init_file = package_dir / "__init__.py"
            init_file.write_text("# package")

            entity_path = EntityPath(file_path="mypackage", entity_name=None)
            result = resolve_entity_path(entity_path, repo_root)

            assert result is not None
            assert result.is_dir()
            assert result == package_dir

    def test_resolve_nonexistent_file_returns_none(self):
        """Test that nonexistent file returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            entity_path = EntityPath(file_path="nonexistent.py", entity_name=None)
            result = resolve_entity_path(entity_path, repo_root)

            assert result is None

    def test_resolve_package_without_init_returns_path(self):
        """Test that package without __init__.py returns directory path (namespace package)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            # Create directory but no __init__.py (namespace package)
            package_dir = repo_root / "notapackage"
            package_dir.mkdir()

            entity_path = EntityPath(file_path="notapackage", entity_name=None)
            result = resolve_entity_path(entity_path, repo_root)

            # Should return the directory path even without __init__.py
            # This allows sync to create __init__.py for namespace packages
            assert result == package_dir

    def test_resolve_with_method_path(self):
        """Test resolving path with method specification."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            test_file = repo_root / "test.py"
            test_file.write_text("class Foo:\n    def bar(self): pass")

            entity_path = EntityPath(file_path="test.py", entity_name="Foo.bar")
            result = resolve_entity_path(entity_path, repo_root)

            assert result is not None
            assert result == test_file


class TestIntegration:
    """Integration tests combining parsing and resolution."""

    def test_parse_and_resolve_full_workflow(self):
        """Test full workflow of parsing and resolving."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)

            # Create test structure
            src_dir = repo_root / "src" / "myapp"
            src_dir.mkdir(parents=True)
            (src_dir / "__init__.py").write_text("")
            test_file = src_dir / "module.py"
            test_file.write_text("class MyClass:\n    def my_method(self): pass")

            # Parse path
            path_str = "src/myapp/module.py:MyClass.my_method"
            entity_path = parse_entity_path(path_str)

            # Resolve path
            resolved = resolve_entity_path(entity_path, repo_root)

            assert resolved is not None
            assert resolved == test_file
            assert entity_path.is_method is True
            assert entity_path.class_name == "MyClass"
            assert entity_path.method_name == "my_method"
