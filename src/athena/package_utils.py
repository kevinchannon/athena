"""Utilities for package detection and manifest generation."""

from pathlib import Path


def is_package(path: Path) -> bool:
    """Check if a path is a Python package.

    A package is a directory containing an __init__.py file.
    Namespace packages (directories without __init__.py) are not packages.

    Args:
        path: Path to check

    Returns:
        True if path is a package, False otherwise
    """
    if not path.is_dir():
        return False

    init_file = path / "__init__.py"
    return init_file.exists()


def get_init_file_path(package_path: Path) -> Path:
    """Get the path to a package's __init__.py file.

    Args:
        package_path: Path to the package directory

    Returns:
        Path to __init__.py
    """
    return package_path / "__init__.py"


def _should_skip_from_manifest(child: Path) -> bool:
    """Check if a path should be excluded from the package manifest."""
    if child.name.startswith("."):
        return True
    if child.name == "__pycache__":
        return True
    if child.name == "__init__.py":
        return True
    return False


def _is_python_module(child: Path) -> bool:
    """Check if a path is a Python module file."""
    return child.is_file() and child.suffix == ".py"


def _is_subpackage(child: Path) -> bool:
    """Check if a path is a Python sub-package."""
    return child.is_dir() and is_package(child)


def get_package_manifest(package_path: Path) -> list[str]:
    """Get sorted manifest of direct children in a package.

    The manifest includes:
    - Python module files (with .py extension, e.g., "module.py")
    - Sub-package directories (without extension, e.g., "subpkg")

    Excludes:
    - __init__.py (it's the package itself)
    - __pycache__ directories
    - Hidden files/directories (starting with .)
    - Non-Python files

    The manifest is deterministically sorted for consistent hashing.

    Args:
        package_path: Path to the package directory

    Returns:
        Sorted list of direct children (module filenames and sub-package names)
    """
    if not package_path.is_dir():
        return []

    manifest = []
    for child in package_path.iterdir():
        if _should_skip_from_manifest(child):
            continue

        if _is_python_module(child):
            manifest.append(child.name)
        elif _is_subpackage(child):
            manifest.append(child.name)

    return sorted(manifest)
