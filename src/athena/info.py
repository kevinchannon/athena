from pathlib import Path

from athena.models import EntityInfo
from athena.parsers import get_parser_for_file
from athena.repository import find_repository_root, get_relative_path


def get_entity_info(
    file_path: str,
    entity_name: str | None = None,
    root: Path | None = None
) -> EntityInfo | None:
    """Get detailed information about an entity in a file.

    Args:
        file_path: Path to file (can be absolute or relative to repo root)
        entity_name: Name of entity, or None for module-level info
        root: Repository root (auto-detected if None)

    Returns:
        EntityInfo object, or None if file/entity not found

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file type not supported
    """
    # Auto-detect repository root if not provided
    if root is None:
        root = find_repository_root(Path.cwd())

    # Resolve file path
    file_path_obj = Path(file_path)
    if not file_path_obj.is_absolute():
        file_path_obj = root / file_path_obj

    # Check file exists
    if not file_path_obj.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

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
