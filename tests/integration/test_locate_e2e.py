import json
import subprocess


def test_locate_command_on_actual_repository():
    """Test the locate command on the actual athena repository."""
    # Locate a known function in our codebase
    result = subprocess.run(
        ["uv", "run", "-m", "athena", "locate", "--json", "find_repository_root"],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    data = json.loads(result.stdout)

    # Should find the find_repository_root function
    assert len(data) >= 1
    assert any(e["kind"] == "function" for e in data)
    assert any("repository.py" in e["path"] for e in data)


def test_locate_class_in_repository():
    """Test locating a class in the actual repository."""
    result = subprocess.run(
        ["uv", "run", "-m", "athena", "locate", "--json", "PythonParser"],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    data = json.loads(result.stdout)

    # Should find the PythonParser class
    assert len(data) >= 1
    classes = [e for e in data if e["kind"] == "class"]
    assert len(classes) >= 1
    assert any("python_parser.py" in e["path"] for e in classes)


def test_locate_nonexistent_entity():
    """Test that searching for nonexistent entity returns empty array."""
    result = subprocess.run(
        ["uv", "run", "-m", "athena", "locate", "--json", "ThisDoesNotExistAnywhere"],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data == []


def test_json_output_can_be_piped():
    """Test that JSON output is valid and can be processed."""
    result = subprocess.run(
        ["uv", "run", "-m", "athena", "locate", "--json", "locate_entity"],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    # Verify it's valid JSON
    data = json.loads(result.stdout)
    assert isinstance(data, list)

    # Verify structure matches expected format
    if len(data) > 0:
        entity = data[0]
        assert "kind" in entity
        assert "path" in entity
        assert "extent" in entity
        assert "start" in entity["extent"]
        assert "end" in entity["extent"]
