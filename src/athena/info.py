from pathlib import Path

from athena.models import EntityInfo, PackageInfo
from athena.parsers import get_parser_for_file
from athena.repository import find_repository_root, get_relative_path


def get_entity_info(
    file_path: str,
    entity_name: str | None = None,
    root: Path | None = None
) -> EntityInfo | None:
    """Get detailed information about an entity in a file or package.

    Args:
        file_path: Path to file or directory (can be absolute or relative to repo root)
        entity_name: Name of entity, or None for module/package-level info
        root: Repository root (auto-detected if None)

    Returns:
        EntityInfo object, or None if file/entity not found

    Raises:
        FileNotFoundError: If file/directory doesn't exist
        ValueError: If file type not supported or directory missing __init__.py
    """
    # Auto-detect repository root if not provided
    if root is None:
        root = find_repository_root(Path.cwd())

    # Resolve file path
    file_path_obj = Path(file_path)
    if not file_path_obj.is_absolute():
        file_path_obj = root / file_path_obj

    # Check path exists
    if not file_path_obj.exists():
        raise FileNotFoundError(f"Path not found: {file_path}")

    # Handle directory (package) case
    if file_path_obj.is_dir():
        if entity_name is not None:
            raise ValueError(f"Cannot specify entity name for package: {file_path}")

        # Look for __init__.py
        init_file = file_path_obj / "__init__.py"
        if not init_file.exists():
            raise ValueError(f"Package missing __init__.py: {file_path}")

        # Get parser and extract module docstring from __init__.py
        parser = get_parser_for_file(init_file)
        if parser is None:
            raise ValueError(f"Cannot parse __init__.py in: {file_path}")

        source_code = init_file.read_text()
        # Get relative path for the directory
        relative_path = get_relative_path(file_path_obj, root)

        # Extract module-level info from __init__.py
        module_info = parser.extract_entity_info(source_code, str(init_file), None)

        # Convert to PackageInfo
        if module_info is not None:
            return PackageInfo(
                path=relative_path,
                summary=module_info.summary if hasattr(module_info, 'summary') else None
            )
        else:
            return PackageInfo(path=relative_path, summary=None)

    # Handle file case
    # Get parser for file
    parser = get_parser_for_file(file_path_obj)
    if parser is None:
        raise ValueError(f"Unsupported file type: {file_path}")

    # Read source code
    source_code = file_path_obj.read_text()

    # Get relative path for EntityInfo.path
    relative_path = get_relative_path(file_path_obj, root)

    # Call parser to extract entity info
    return parser.extract_entity_info(source_code, relative_path, entity_name)
