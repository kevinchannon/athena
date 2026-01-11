"""MCP configuration management for Claude Code integration."""

import json
import os
import platform
from pathlib import Path


def get_claude_config_path() -> Path:
    """Get the Claude Code configuration file path for the current OS.

    Returns:
        Path to claude_desktop_config.json

    Raises:
        RuntimeError: If OS is not supported
    """
    system = platform.system()

    if system == "Darwin":  # macOS
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    elif system == "Linux":
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"
    elif system == "Windows":
        return Path(os.environ["APPDATA"]) / "Claude" / "claude_desktop_config.json"
    else:
        raise RuntimeError(f"Unsupported operating system: {system}")


def install_mcp_config() -> tuple[bool, str]:
    """Install MCP server configuration for Claude Code.

    Returns:
        Tuple of (success, message)
    """
    try:
        config_path = get_claude_config_path()

        # Ensure config directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing config or create new one
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        else:
            config = {}

        # Ensure mcpServers section exists
        if "mcpServers" not in config:
            config["mcpServers"] = {}

        # Check if ack is already configured
        if "ack" in config["mcpServers"]:
            return (False, "MCP server already configured")

        # Add ack MCP server configuration
        config["mcpServers"]["ack"] = {
            "command": "ack",
            "args": ["mcp-server"]
        }

        # Write updated config
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

        return (True, f"MCP server configured at {config_path}")

    except Exception as e:
        return (False, f"Failed to install MCP config: {e}")


def uninstall_mcp_config() -> tuple[bool, str]:
    """Remove MCP server configuration from Claude Code.

    Returns:
        Tuple of (success, message)
    """
    try:
        config_path = get_claude_config_path()

        if not config_path.exists():
            return (False, "Claude config file not found")

        # Load existing config
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        # Check if ack is configured
        if "mcpServers" not in config or "ack" not in config["mcpServers"]:
            return (False, "MCP server not configured")

        # Remove ack configuration
        del config["mcpServers"]["ack"]

        # Write updated config
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

        return (True, f"MCP server removed from {config_path}")

    except Exception as e:
        return (False, f"Failed to uninstall MCP config: {e}")
