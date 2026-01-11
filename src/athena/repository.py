from pathlib import Path
from typing import Iterator


EXCLUDED_DIRS = {
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "build",
    "dist",
    ".git",
    ".tox",
    "vendor",
}


class RepositoryNotFoundError(Exception):
    """Raised when no git repository is found."""
    pass


def find_repository_root(start_path: Path = Path.cwd()) -> Path:
    """Find the root of the git repository by walking up the directory tree.

    Args:
        start_path: The directory to start searching from (defaults to current directory)

    Returns:
        Path to the repository root (the directory containing .git/)

    Raises:
        RepositoryNotFoundError: If no .git directory is found
    """
    current = start_path.resolve()

    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent

    if (current / ".git").exists():
        return current

    raise RepositoryNotFoundError(
        f"No git repository found from {start_path}"
    )


def find_python_files(root: Path) -> Iterator[Path]:
    """Find all Python files in the repository, excluding common directories.

    Args:
        root: The repository root directory to search

    Yields:
        Path objects for each .py file found
    """
    for path in root.rglob("*.py"):
        if any(excluded in path.parts for excluded in EXCLUDED_DIRS):
            continue
        yield path


def get_relative_path(file_path: Path, root: Path) -> str:
    """Convert an absolute file path to a POSIX-style relative path from root.

    Args:
        file_path: Absolute path to a file
        root: Repository root directory

    Returns:
        POSIX-style relative path as a string
    """
    return file_path.relative_to(root).as_posix()
