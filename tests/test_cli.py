import json
import re

from typer.testing import CliRunner

from athena.cli import app

runner = CliRunner()


def test_app_has_locate_command():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "locate" in result.stdout


def test_app_has_mcp_server_command():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "mcp-server" in result.stdout


def test_app_has_install_mcp_command():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "install-mcp" in result.stdout


def test_app_has_uninstall_mcp_command():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "uninstall-mcp" in result.stdout


def test_locate_command_requires_entity_name():
    # Should fail without entity name argument
    result = runner.invoke(app, ["locate"])

    assert result.exit_code != 0


def test_locate_command_shows_help():
    result = runner.invoke(app, ["locate", "--help"])

    assert result.exit_code == 0
    assert "entity_name" in result.stdout.lower()
    assert "locate" in result.stdout.lower()


def test_locate_command_outputs_valid_json(tmp_path, monkeypatch):
    # Create a test repository
    test_file = tmp_path / "test.py"
    test_file.write_text("def target():\n    pass\n")
    (tmp_path / ".git").mkdir()

    # Change to temp directory
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["locate", "target"])

    assert result.exit_code == 0
    # Verify it's valid JSON
    data = json.loads(result.stdout)
    assert isinstance(data, list)


def test_locate_command_returns_empty_array_when_not_found(tmp_path, monkeypatch):
    # Create a test repository
    test_file = tmp_path / "test.py"
    test_file.write_text("def other_function():\n    pass\n")
    (tmp_path / ".git").mkdir()

    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["locate", "nonexistent"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data == []


def test_version_flag():
    expected_output_pattern = r"^athena version \d+\.\d+\.\d+(\.[a-z0-9]+)?(\+local)?\n"

    result = runner.invoke(app, ["-v"])
    assert result.exit_code == 0
    assert re.match(expected_output_pattern, result.stdout)

    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert re.match(expected_output_pattern, result.stdout)


def test_app_has_info_command():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "info" in result.stdout


def test_info_command_requires_location():
    # Should fail without location argument
    result = runner.invoke(app, ["info"])

    assert result.exit_code != 0


def test_info_command_shows_help():
    result = runner.invoke(app, ["info", "--help"])

    assert result.exit_code == 0
    assert "location" in result.stdout.lower()


def test_info_command_with_entity_name(tmp_path, monkeypatch):
    # Create a test repository
    test_file = tmp_path / "test.py"
    test_file.write_text('''def validateSession(token: str = "abc") -> bool:
    """Validates token."""
    return True
''')
    (tmp_path / ".git").mkdir()

    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["info", "test.py:validateSession"])

    assert result.exit_code == 0
    # Verify it's valid JSON with discriminated structure
    data = json.loads(result.stdout)
    assert "function" in data
    func = data["function"]
    assert func["path"] == "test.py"
    assert func["sig"]["name"] == "validateSession"
    assert len(func["sig"]["args"]) == 1
    assert func["sig"]["args"][0]["name"] == "token"
    assert func["sig"]["args"][0]["type"] == "str"
    assert func["sig"]["return_type"] == "bool"
    assert func["summary"] == "Validates token."


def test_info_command_module_level(tmp_path, monkeypatch):
    # Create a test repository
    test_file = tmp_path / "test.py"
    test_file.write_text('''"""Module docstring."""

def some_func():
    pass
''')
    (tmp_path / ".git").mkdir()

    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["info", "test.py"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "module" in data
    mod = data["module"]
    assert mod["path"] == "test.py"
    assert mod["summary"] == "Module docstring."


def test_info_command_entity_not_found(tmp_path, monkeypatch):
    test_file = tmp_path / "test.py"
    test_file.write_text("def hello():\n    pass\n")
    (tmp_path / ".git").mkdir()

    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["info", "test.py:nonexistent"])

    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_info_command_file_not_found(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()

    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["info", "nonexistent.py:hello"])

    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_info_command_without_docstring(tmp_path, monkeypatch):
    test_file = tmp_path / "test.py"
    test_file.write_text('''def hello():
    pass
''')
    (tmp_path / ".git").mkdir()

    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["info", "test.py:hello"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "function" in data
    func = data["function"]
    # summary should be omitted when None
    assert "summary" not in func


def test_info_command_package(tmp_path, monkeypatch):
    """Test info command with a package (directory with __init__.py)."""
    # Create package directory
    package_dir = tmp_path / "mypackage"
    package_dir.mkdir()
    init_file = package_dir / "__init__.py"
    init_file.write_text('"""This is my test package."""')
    (tmp_path / ".git").mkdir()

    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["info", "mypackage"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "package" in data
    pkg = data["package"]
    assert pkg["path"] == "mypackage"
    assert pkg["summary"] == "This is my test package."
    # Package should not have extent or sig fields
    assert "extent" not in pkg
    assert "sig" not in pkg


def test_info_command_package_no_docstring(tmp_path, monkeypatch):
    """Test info command with a package that has no docstring."""
    # Create package directory
    package_dir = tmp_path / "mypackage"
    package_dir.mkdir()
    init_file = package_dir / "__init__.py"
    init_file.write_text('# Just a comment')
    (tmp_path / ".git").mkdir()

    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["info", "mypackage"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "package" in data
    pkg = data["package"]
    assert pkg["path"] == "mypackage"
    # summary should be omitted when None
    assert "summary" not in pkg


def test_info_command_package_missing_init(tmp_path, monkeypatch):
    """Test info command with directory missing __init__.py."""
    # Create directory without __init__.py
    package_dir = tmp_path / "mypackage"
    package_dir.mkdir()
    (tmp_path / ".git").mkdir()

    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["info", "mypackage"])

    assert result.exit_code == 1
    assert "missing __init__.py" in result.output.lower()


