from pathlib import Path

from athena.locate import locate_entity


def test_locate_entity_in_simple_file(tmp_path):
    # Create a test Python file
    test_file = tmp_path / "example.py"
    test_file.write_text("""def hello():
    print("world")

def goodbye():
    print("farewell")
""")

    # Create .git directory to make it a repository
    (tmp_path / ".git").mkdir()

    # Locate the hello function
    entities = locate_entity("hello", root=tmp_path)

    # Should find exactly one entity with name="hello"
    assert len(entities) == 1
    assert entities[0].name == "hello"
    assert entities[0].kind == "function"


def test_locate_entity_returns_correct_path(tmp_path):
    # Create a test file in a subdirectory
    subdir = tmp_path / "src"
    subdir.mkdir()
    test_file = subdir / "module.py"
    test_file.write_text("""def my_function():
    pass
""")

    (tmp_path / ".git").mkdir()

    entities = locate_entity("my_function", root=tmp_path)

    assert len(entities) == 1
    assert entities[0].path == "src/module.py"
    assert entities[0].kind == "function"


def test_locate_entity_in_class(tmp_path):
    test_file = tmp_path / "classes.py"
    test_file.write_text("""class MyClass:
    def my_method(self):
        pass
""")

    (tmp_path / ".git").mkdir()

    entities = locate_entity("my_method", root=tmp_path)

    # Should find both the class and the method
    assert len(entities) >= 1
    methods = [e for e in entities if e.kind == "method"]
    assert len(methods) == 1


def test_locate_entity_across_multiple_files(tmp_path):
    file1 = tmp_path / "file1.py"
    file1.write_text("def shared_name():\n    pass\n")

    file2 = tmp_path / "file2.py"
    file2.write_text("def shared_name():\n    pass\n")

    (tmp_path / ".git").mkdir()

    entities = locate_entity("shared_name", root=tmp_path)

    # Should find entities from both files
    assert len(entities) == 2
    paths = {e.path for e in entities}
    assert "file1.py" in paths
    assert "file2.py" in paths


def test_locate_entity_skips_unparseable_files(tmp_path):
    # Create a valid file
    good_file = tmp_path / "good.py"
    good_file.write_text("def target_function():\n    pass\n")

    # Create an unparseable file (invalid UTF-8)
    bad_file = tmp_path / "bad.py"
    bad_file.write_bytes(b"\xff\xfe Invalid UTF-8")

    (tmp_path / ".git").mkdir()

    # Should still find the entity in the good file
    entities = locate_entity("target_function", root=tmp_path)

    assert len(entities) == 1
    assert entities[0].path == "good.py"

