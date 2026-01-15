from pathlib import Path

from athena.models import Entity
from athena.parsers import get_parser_for_file
from athena.repository import find_python_files, find_repository_root, get_relative_path


def locate_entity(name: str, root: Path | None = None) -> list[Entity]:
    """Locate all entities with the given name in the repository.

    For methods, the search matches both the full qualified name (ClassName.method_name)
    and the short method name (method_name).

    Args:
        name: The entity name to search for
        root: Repository root (defaults to auto-detected root)

    Returns:
        List of Entity objects matching the given name
    """
    if root is None:
        root = find_repository_root()

    entities = []

    for file_path in find_python_files(root):
        parser = get_parser_for_file(file_path)
        if parser is None:
            continue

        try:
            source_code = file_path.read_text(encoding="utf-8")
            relative_path = get_relative_path(file_path, root)

            file_entities = parser.extract_entities(source_code, relative_path)

            # Filter entities by name
            for entity in file_entities:
                # Exact match
                if entity.name == name:
                    entities.append(entity)
                # For methods, also match the short name (without class prefix)
                elif entity.kind == "method" and "." in entity.name:
                    method_name = entity.name.split(".", 1)[1]
                    if method_name == name:
                        entities.append(entity)
        except Exception:
            # Skip files that can't be read or parsed
            # This allows the scan to continue even if some files fail
            continue

    return entities
