import json
import re
from pathlib import Path

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


def test_app_has_sync_command():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "sync" in result.stdout


def test_locate_command_requires_entity_name():
    # Should fail without entity name argument
    result = runner.invoke(app, ["locate"])

    assert result.exit_code != 0


def test_locate_command_shows_help():
    result = runner.invoke(app, ["locate", "--help"])

    assert result.exit_code == 0
    assert "entity_name" in result.stdout.lower()
    assert "locate" in result.stdout.lower()


def test_locate_command_outputs_table_by_default():
    # Test with actual repository
    result = runner.invoke(app, ["locate", "locate_entity"])

    assert result.exit_code == 0
    # Check that output is a table (contains table markers)
    assert "Kind" in result.stdout
    assert "Path" in result.stdout
    assert "Extent" in result.stdout
    assert "function" in result.stdout


def test_locate_command_outputs_valid_json_with_flag():
    # Test with actual repository
    result = runner.invoke(app, ["locate", "--json", "locate_entity"])

    assert result.exit_code == 0
    # Verify it's valid JSON
    data = json.loads(result.stdout)
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["kind"] == "function"


def test_locate_command_json_short_flag():
    # Test with actual repository
    result = runner.invoke(app, ["locate", "-j", "locate_entity"])

    assert result.exit_code == 0
    # Verify it's valid JSON
    data = json.loads(result.stdout)
    assert isinstance(data, list)


def test_locate_command_returns_empty_table_when_not_found():
    # Search for something that definitely doesn't exist
    result = runner.invoke(app, ["locate", "ThisFunctionDefinitelyDoesNotExist"])

    assert result.exit_code == 0
    # Table headers should still be present even when empty
    assert "Kind" in result.stdout or result.stdout == ""


def test_locate_command_returns_empty_json_when_not_found():
    # Search for something that definitely doesn't exist
    result = runner.invoke(app, ["locate", "--json", "ThisFunctionDefinitelyDoesNotExist"])

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


def test_sync_command_shows_help():
    """Test that sync command shows help."""
    result = runner.invoke(app, ["sync", "--help"])

    assert result.exit_code == 0
    assert "Update @athena hash tags" in result.stdout
    # Check for "force" and "recursive" options (may have formatting/ANSI codes)
    assert "force" in result.stdout.lower()
    assert "recursive" in result.stdout.lower()


def test_sync_command_single_function():
    """Test syncing a single function."""
    with runner.isolated_filesystem():
        Path("test.py").write_text(
            """def foo():
    return 1
"""
        )
        Path(".git").mkdir()

        result = runner.invoke(app, ["sync", "test.py:foo"], catch_exceptions=False)

        # Debug output
        if result.exit_code != 1:
            print(f"Exit code: {result.exit_code}")
            print(f"Stdout: {result.stdout}")
            print(f"Exception: {result.exception if hasattr(result, 'exception') else 'None'}")

        assert result.exit_code == 1  # 1 entity updated
        assert "Updated 1 entity" in result.stdout

        # Check file was updated
        updated_code = Path("test.py").read_text()
        assert "@athena:" in updated_code


def test_sync_command_with_force_flag():
    """Test sync with --force flag."""
    with runner.isolated_filesystem():
        Path("test.py").write_text(
            """def foo():
    return 1
"""
        )
        Path(".git").mkdir()

        # First sync
        runner.invoke(app, ["sync", "test.py:foo"])

        # Second sync without force - should not update
        result = runner.invoke(app, ["sync", "test.py:foo"])
        assert result.exit_code == 0
        assert "No updates needed" in result.stdout

        # Third sync with force - should update
        result = runner.invoke(app, ["sync", "test.py:foo", "--force"])
        assert result.exit_code == 1
        assert "Updated 1 entity" in result.stdout


