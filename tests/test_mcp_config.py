"""Tests for MCP configuration management."""

import json
import platform
from pathlib import Path

import pytest

from athena.mcp_config import (
    get_claude_config_path,
    install_mcp_config,
    uninstall_mcp_config,
)


def test_get_claude_config_path():
    """Test that config path is correct for current OS."""
    path = get_claude_config_path()
    assert path.name == "claude_desktop_config.json"

    system = platform.system()
    if system == "Darwin":
        assert "Library/Application Support/Claude" in str(path)
    elif system == "Linux":
        assert ".config/Claude" in str(path)
    elif system == "Windows":
        assert "Claude" in str(path)


def test_install_mcp_config_creates_new_config(tmp_path, monkeypatch):
    """Test installing MCP config when no config exists."""
    config_path = tmp_path / "claude_desktop_config.json"

    monkeypatch.setattr(
        "athena.mcp_config.get_claude_config_path", lambda: config_path
    )

    success, message = install_mcp_config()

    assert success
    assert str(config_path) in message
    assert config_path.exists()

    # Verify config content
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    assert "mcpServers" in config
    assert "ack" in config["mcpServers"]
    assert config["mcpServers"]["ack"]["command"] == "ack"
    assert config["mcpServers"]["ack"]["args"] == ["mcp-server"]


def test_install_mcp_config_updates_existing_config(tmp_path, monkeypatch):
    """Test installing MCP config when config already exists."""
    config_path = tmp_path / "claude_desktop_config.json"

    # Create existing config with other servers
    existing_config = {
        "mcpServers": {
            "other-server": {"command": "other", "args": []}
        }
    }
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(existing_config, f)

    monkeypatch.setattr(
        "athena.mcp_config.get_claude_config_path", lambda: config_path
    )

    success, message = install_mcp_config()

    assert success

    # Verify config preserves existing servers
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    assert "other-server" in config["mcpServers"]
    assert "ack" in config["mcpServers"]


def test_install_mcp_config_detects_existing_ack(tmp_path, monkeypatch):
    """Test that install detects if ack is already configured."""
    config_path = tmp_path / "claude_desktop_config.json"

    # Create config with ack already present
    existing_config = {
        "mcpServers": {
            "ack": {"command": "ack", "args": ["mcp-server"]}
        }
    }
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(existing_config, f)

    monkeypatch.setattr(
        "athena.mcp_config.get_claude_config_path", lambda: config_path
    )

    success, message = install_mcp_config()

    assert not success
    assert "already configured" in message


def test_uninstall_mcp_config_removes_ack(tmp_path, monkeypatch):
    """Test uninstalling MCP config."""
    config_path = tmp_path / "claude_desktop_config.json"

    # Create config with ack
    existing_config = {
        "mcpServers": {
            "ack": {"command": "ack", "args": ["mcp-server"]},
            "other-server": {"command": "other", "args": []}
        }
    }
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(existing_config, f)

    monkeypatch.setattr(
        "athena.mcp_config.get_claude_config_path", lambda: config_path
    )

    success, message = uninstall_mcp_config()

    assert success
    assert str(config_path) in message

    # Verify ack is removed but other servers remain
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    assert "ack" not in config["mcpServers"]
    assert "other-server" in config["mcpServers"]


def test_uninstall_mcp_config_when_not_configured(tmp_path, monkeypatch):
    """Test uninstalling when ack is not configured."""
    config_path = tmp_path / "claude_desktop_config.json"

    # Create config without ack
    existing_config = {
        "mcpServers": {
            "other-server": {"command": "other", "args": []}
        }
    }
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(existing_config, f)

    monkeypatch.setattr(
        "athena.mcp_config.get_claude_config_path", lambda: config_path
    )

    success, message = uninstall_mcp_config()

    assert not success
    assert "not configured" in message


def test_uninstall_mcp_config_when_file_not_found(tmp_path, monkeypatch):
    """Test uninstalling when config file doesn't exist."""
    config_path = tmp_path / "nonexistent.json"

    monkeypatch.setattr(
        "athena.mcp_config.get_claude_config_path", lambda: config_path
    )

    success, message = uninstall_mcp_config()

    assert not success
    assert "not found" in message
