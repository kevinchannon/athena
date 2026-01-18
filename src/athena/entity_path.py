"""Entity path parsing and resolution.

Entity path format: dir/package/module:class.method
Examples:
  - src/athena/cli.py:app
  - src/athena/parsers/python_parser.py:PythonParser.parse_athena_tag
  - models.py:Entity
  - src/athena
"""

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EntityPath:
    """Represents a parsed entity path.

    Attributes:
        file_path: Path to the file (without entity specification)
        entity_name: Name of the entity within the file (class.method or function)
                    None for module-level or package-level operations
    """

    file_path: str
    entity_name: str | None = None

    @property
    def is_package(self) -> bool:
        """Check if this path represents a package (directory)."""
        return not self.file_path.endswith(".py") and self.entity_name is None

    @property
    def is_module(self) -> bool:
        """Check if this path represents a module (file without entity)."""
        return self.file_path.endswith(".py") and self.entity_name is None

    @property
    def is_class(self) -> bool:
        """Check if this path represents a class (no dot in entity name)."""
        return self.entity_name is not None and "." not in self.entity_name

    @property
    def is_method(self) -> bool:
        """Check if this path represents a method (dot in entity name)."""
        return self.entity_name is not None and "." in self.entity_name

    @property
    def class_name(self) -> str | None:
        """Extract class name if this is a method path."""
        if self.is_method:
            return self.entity_name.split(".")[0]
        return None

    @property
    def method_name(self) -> str | None:
        """Extract method name if this is a method path."""
        if self.is_method:
            return self.entity_name.split(".")[1]
        return None


def parse_entity_path(path: str) -> EntityPath:
    """Parse an entity path string into components.

    Format: [directory/]file.py[:entity[.subentity]]

    Args:
        path: Entity path string to parse

    Returns:
        EntityPath object with parsed components

    Raises:
        ValueError: If path format is invalid

    Examples:
        >>> parse_entity_path("src/foo/bar.py:Baz.bax")
        EntityPath(file_path='src/foo/bar.py', entity_name='Baz.bax')

        >>> parse_entity_path("models.py:Entity")
        EntityPath(file_path='models.py', entity_name='Entity')

        >>> parse_entity_path("src/athena/cli.py")
        EntityPath(file_path='src/athena/cli.py', entity_name=None)

        >>> parse_entity_path("src/athena")
        EntityPath(file_path='src/athena', entity_name=None)
    """
    if not path or not path.strip():
        raise ValueError("Entity path cannot be empty")

    # Split on colon to separate file path from entity name
    if ":" in path:
        file_path, entity_name = path.split(":", 1)
        entity_name = entity_name.strip()
        if not entity_name:
            entity_name = None
    else:
        file_path = path
        entity_name = None

    file_path = file_path.strip()

    if not file_path:
        raise ValueError("File path component cannot be empty")

    return EntityPath(file_path=file_path, entity_name=entity_name)


def resolve_entity_path(entity_path: EntityPath, repo_root: Path) -> Path | None:
    """Resolve an EntityPath to an actual file system path.

    Args:
        entity_path: Parsed entity path
        repo_root: Root directory of the repository

    Returns:
        Resolved Path object if file/directory exists, None otherwise
    """
    # Construct full path
    full_path = repo_root / entity_path.file_path

    # If it's meant to be a package, check if it's a valid directory
    if entity_path.is_package:
        # Check if the directory exists
        if not full_path.is_dir():
            return None

        # Return the directory path for packages
        # We allow packages without __init__.py (namespace packages)
        # The sync logic can create __init__.py if needed
        return full_path

    # For files, check if path exists
    if full_path.exists():
        return full_path

    return None
