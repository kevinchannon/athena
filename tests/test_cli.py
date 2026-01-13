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


def test_version_flag_short():
    result = runner.invoke(app, ["-v"])

    assert result.exit_code == 0
    assert re.match(r"^athena version \d+\.\d+\.\d+(-[a-z0-9]+)?(\+local)?\n", result.stdout)


def test_version_flag_long():
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert re.match(r"athena version \d+\.\d+\.\d+(-[a-z0-9]+)?\n", result.stdout)


