"""Status command - check entity docstring hash synchronization state."""

from pathlib import Path

from athena.entity_path import EntityPath, parse_entity_path
from athena.models import EntityStatus
from athena.sync import collect_sub_entities, inspect_entity


def check_status(entity_path_str: str, repo_root: Path) -> list[EntityStatus]:
    """Check status of a single entity.

    Args:
        entity_path_str: Entity path string (e.g., "src/foo.py:Bar")
        repo_root: Repository root directory

    Returns:
        List containing single EntityStatus

    Raises:
        FileNotFoundError: If entity file doesn't exist
        ValueError: If entity is not found in file or path is invalid
        NotImplementedError: For package/module level status
    """
    status = inspect_entity(entity_path_str, repo_root)
    return [status]


def check_status_recursive(entity_path_str: str, repo_root: Path) -> list[EntityStatus]:
    """Check status of an entity and all its sub-entities recursively.

    For modules: checks all functions, classes, and methods
    For packages: checks all modules and their entities
    For classes: checks the class and all its methods
    For functions/methods: checks only that entity

    Args:
        entity_path_str: Entity path string
        repo_root: Repository root directory

    Returns:
        List of EntityStatus for all entities

    Raises:
        FileNotFoundError: If entity file doesn't exist
        ValueError: If entity is not found in file or path is invalid
    """
    entity_path = parse_entity_path(entity_path_str)

    entities_to_check = []

    if entity_path.is_package or entity_path.is_module:
        entities_to_check = collect_sub_entities(entity_path, repo_root)
    else:
        if entity_path.is_class:
            entities_to_check.append(entity_path_str)
            entities_to_check.extend(collect_sub_entities(entity_path, repo_root))
        else:
            entities_to_check.append(entity_path_str)

    statuses = []
    for entity in entities_to_check:
        try:
            status = inspect_entity(entity, repo_root)
            statuses.append(status)
        except (ValueError, FileNotFoundError) as e:
            print(f"Warning: Failed to inspect {entity}: {e}")

    return statuses


def filter_out_of_sync(statuses: list[EntityStatus]) -> list[EntityStatus]:
    """Filter list to only out-of-sync entities.

    An entity is out-of-sync if:
    - It has no recorded hash (None)
    - The recorded hash doesn't match the calculated hash

    Args:
        statuses: List of EntityStatus

    Returns:
        Filtered list containing only out-of-sync entities
    """
    return [
        s for s in statuses
        if s.recorded_hash is None or s.recorded_hash != s.calculated_hash
    ]
