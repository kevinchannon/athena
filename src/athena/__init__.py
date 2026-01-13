"""Athena - A semantic code analysis tool designed to help Claude Code navigate repositories efficiently while dramatically reducing token consumption."""

try:
    from importlib.metadata import version

    __version__ = version("athena")
except Exception:
    __version__ = "0.0.0.dev0+local"  # Fallback for development
