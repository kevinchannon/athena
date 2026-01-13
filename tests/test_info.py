from pathlib import Path

import pytest

from athena.info import get_entity_info


def test_get_function_info(tmp_path):
    """Test getting info for a function with entity name."""
    # Create a temporary git repository
    (tmp_path / ".git").mkdir()

    # Create a test file
    test_file = tmp_path / "test.py"
    test_file.write_text('''def hello(name: str = "World") -> str:
    """Greet someone."""
    return f"Hello, {name}!"
''')

    # Get function info
    info = get_entity_info(str(test_file), "hello", root=tmp_path)

    assert info is not None
    assert info.path == "test.py"
    assert info.sig is not None
    assert info.sig.name == "hello"
    assert len(info.sig.args) == 1
    assert info.sig.args[0].name == "name"
    assert info.sig.args[0].type == "str"
    assert info.sig.return_type == "str"
    assert info.summary == "Greet someone."


def test_get_method_info(tmp_path):
    """Test getting info for a method with entity name."""
    (tmp_path / ".git").mkdir()

    test_file = tmp_path / "test.py"
    test_file.write_text('''class Calculator:
    def add(self, x: int, y: int) -> int:
        """Add two numbers."""
        return x + y
''')

    info = get_entity_info(str(test_file), "add", root=tmp_path)

    assert info is not None
    assert info.sig is not None
    assert info.sig.name == "add"
    assert len(info.sig.args) == 3  # self, x, y
    assert info.summary == "Add two numbers."


def test_get_module_info(tmp_path):
    """Test getting module info without entity name."""
    (tmp_path / ".git").mkdir()

    test_file = tmp_path / "test.py"
    test_file.write_text('''"""This is a test module."""

def some_function():
    pass
''')

    info = get_entity_info(str(test_file), None, root=tmp_path)

    assert info is not None
    assert info.path == "test.py"
    assert info.sig is None  # Modules don't have signatures
    assert info.summary == "This is a test module."


def test_entity_not_found(tmp_path):
    """Test that None is returned when entity not found."""
    (tmp_path / ".git").mkdir()

    test_file = tmp_path / "test.py"
    test_file.write_text('''def hello():
    pass
''')

    info = get_entity_info(str(test_file), "nonexistent", root=tmp_path)

    assert info is None


def test_file_not_found(tmp_path):
    """Test that FileNotFoundError is raised for missing file."""
    (tmp_path / ".git").mkdir()

    with pytest.raises(FileNotFoundError):
        get_entity_info(str(tmp_path / "nonexistent.py"), "hello", root=tmp_path)


def test_unsupported_file_type(tmp_path):
    """Test that ValueError is raised for unsupported file type."""
    (tmp_path / ".git").mkdir()

    test_file = tmp_path / "test.txt"
    test_file.write_text("some text")

    with pytest.raises(ValueError):
        get_entity_info(str(test_file), "hello", root=tmp_path)


def test_relative_path(tmp_path):
    """Test that relative paths work correctly."""
    (tmp_path / ".git").mkdir()

    test_file = tmp_path / "src" / "test.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text('''def hello():
    """A function."""
    pass
''')

    # Use relative path from root
    info = get_entity_info("src/test.py", "hello", root=tmp_path)

    assert info is not None
    assert info.path == "src/test.py"
    assert info.summary == "A function."
