"""Parser module for extracting entities from source code"""
from pathlib import Path

from athena.parsers.base import BaseParser
from athena.parsers.python_parser import PythonParser


def get_parser_for_file(file_path: Path) -> BaseParser | None:
    """Get the appropriate parser for a file based on its extension.

    Args:
        file_path: Path to the source file

    Returns:
        Parser instance if the file type is supported, None otherwise
    """
    extension = file_path.suffix.lower()

    if extension == ".py":
        return PythonParser()

    return None
