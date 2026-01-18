"""Core sync logic for updating @athena tags in docstrings."""

import sys
from pathlib import Path

from athena.docstring_updater import update_docstring_in_source
from athena.entity_path import EntityPath, parse_entity_path, resolve_entity_path
from athena.hashing import compute_class_hash, compute_function_hash, compute_module_hash, compute_package_hash
from athena.module_docstring_updater import extract_module_docstring, update_module_docstring
from athena.models import EntityStatus, Location
from athena.package_utils import get_init_file_path, get_package_manifest
from athena.parsers.python_parser import PythonParser


def should_exclude_path(path: Path, repo_root: Path) -> bool:
    """Check if a path should be excluded from sync operations.

    Excludes:
    - athena package itself (prevents self-modification)
    - virtualenvs (.venv, venv, etc.)
    - site-packages
    - Python installation directories

    Args:
        path: Path to check
        repo_root: Repository root directory

    Returns:
        True if path should be excluded, False otherwise
    """
    # Convert to absolute paths for comparison (resolves symlinks)
    abs_path = path.resolve()
    abs_repo_root = repo_root.resolve()

    # Exclude virtualenvs
    parts = abs_path.parts
    if any(part in ['.venv', 'venv', '.virtualenv', 'virtualenv'] for part in parts):
        return True

    # Exclude site-packages
    if 'site-packages' in parts:
        return True

    # Exclude Python installation directories
    sys_prefix = Path(sys.prefix).resolve()
    try:
        abs_path.relative_to(sys_prefix)
        return True
    except ValueError:
        pass

    # Exclude athena package itself
    try:
        rel_path = abs_path.relative_to(abs_repo_root)
        rel_parts = rel_path.parts
        # Check for src/athena/ pattern
        if len(rel_parts) >= 2 and rel_parts[0] == 'src' and rel_parts[1] == 'athena':
            return True
        # Check for athena/ pattern at root (but only if it's the actual athena package)
        # We need to be careful not to exclude user files that happen to be in a directory called "athena"
        # Only exclude if it's actually the athena package with __init__.py
        if rel_parts and rel_parts[0] == 'athena':
            potential_package = abs_repo_root / 'athena'
            if potential_package.is_dir() and (potential_package / '__init__.py').exists():
                return True
    except ValueError as e:
        pass

    return False


def needs_update(current_hash: str | None, computed_hash: str, force: bool) -> bool:
    """Determine if an entity needs hash update.

    Args:
        current_hash: Current hash from docstring (None if no tag)
        computed_hash: Newly computed hash from code
        force: If True, always update regardless of match

    Returns:
        True if update is needed, False otherwise
    """
    if force:
        return True

    if current_hash is None:
        # No existing hash, needs update
        return True

    # Update if hashes don't match
    return current_hash != computed_hash


def inspect_entity(entity_path_str: str, repo_root: Path) -> EntityStatus:
    """Inspect an entity and return its status information.

    This function analyzes an entity and computes its current state:
    - Resolves the entity path to a file
    - Finds the entity in the AST
    - Computes the hash from the AST
    - Extracts the recorded hash from the docstring
    - Determines entity kind and extent

    Args:
        entity_path_str: Entity path string (e.g., "src/foo.py:Bar")
        repo_root: Repository root directory

    Returns:
        EntityStatus containing all status information

    Raises:
        FileNotFoundError: If entity file doesn't exist
        ValueError: If entity is not found in file or path is invalid
        NotImplementedError: For package/module level inspection
    """
    entity_path = parse_entity_path(entity_path_str)

    resolved_path = resolve_entity_path(entity_path, repo_root)
    if resolved_path is None or not resolved_path.exists():
        raise FileNotFoundError(f"Entity file not found: {entity_path.file_path}")

    if should_exclude_path(resolved_path, repo_root):
        raise ValueError(f"Cannot inspect excluded path: {entity_path.file_path}")

    if entity_path.is_package:
        # Package-level inspection
        init_file_path = get_init_file_path(resolved_path)

        # Read __init__.py (or use empty string if it doesn't exist)
        if init_file_path.exists():
            init_source_code = init_file_path.read_text()
        else:
            init_source_code = ""

        # Get package manifest
        manifest = get_package_manifest(resolved_path)

        # Compute package hash
        computed_hash = compute_package_hash(init_source_code, manifest)

        # Extract package docstring from __init__.py
        current_docstring = extract_module_docstring(init_source_code) if init_source_code else None
        if current_docstring:
            current_docstring = current_docstring.strip()

        # Parse @athena tag from docstring
        parser = PythonParser()
        current_hash = (
            parser.parse_athena_tag(current_docstring) if current_docstring else None
        )

        # Package has no line extent (it's a directory)
        # Use a dummy extent for compatibility
        extent = Location(start=0, end=0)

        return EntityStatus(
            kind="package",
            path=entity_path_str,
            extent=extent,
            recorded_hash=current_hash,
            calculated_hash=computed_hash
        )

    source_code = resolved_path.read_text()
    parser = PythonParser()
    tree = parser.parser.parse(bytes(source_code, "utf8"))
    root_node = tree.root_node

    if entity_path.is_module:
        # Module-level inspection
        computed_hash = compute_module_hash(source_code)

        # Extract module docstring
        current_docstring = extract_module_docstring(source_code)
        if current_docstring:
            current_docstring = current_docstring.strip()

        # Parse @athena tag from docstring
        current_hash = (
            parser.parse_athena_tag(current_docstring) if current_docstring else None
        )

        # Module extent is entire file (0-indexed lines)
        lines = source_code.splitlines()
        extent = Location(
            start=0,
            end=len(lines) - 1 if lines else 0
        )

        return EntityStatus(
            kind="module",
            path=entity_path_str,
            extent=extent,
            recorded_hash=current_hash,
            calculated_hash=computed_hash
        )

    entity_node = None
    entity_extent_node = None

    for child in root_node.children:
        if child.type == "function_definition":
            name_node = child.child_by_field_name("name")
            if name_node:
                name = parser._extract_text(
                    source_code, name_node.start_byte, name_node.end_byte
                )
                if name == entity_path.entity_name:
                    entity_node = child
                    entity_extent_node = child
                    break

        elif child.type == "decorated_definition":
            for subchild in child.children:
                if subchild.type == "function_definition":
                    name_node = subchild.child_by_field_name("name")
                    if name_node:
                        name = parser._extract_text(
                            source_code, name_node.start_byte, name_node.end_byte
                        )
                        if name == entity_path.entity_name:
                            entity_node = subchild
                            entity_extent_node = child
                            break
                elif subchild.type == "class_definition":
                    name_node = subchild.child_by_field_name("name")
                    if name_node:
                        name = parser._extract_text(
                            source_code, name_node.start_byte, name_node.end_byte
                        )
                        if name == entity_path.entity_name:
                            entity_node = subchild
                            entity_extent_node = child
                            break

                        # Check if we're looking for a method within this decorated class
                        if entity_path.is_method and name == entity_path.class_name:
                            body = subchild.child_by_field_name("body")
                            if body:
                                for item in body.children:
                                    method_node = None
                                    method_extent_node = None

                                    if item.type == "function_definition":
                                        method_node = item
                                        method_extent_node = item
                                    elif item.type == "decorated_definition":
                                        for subitem in item.children:
                                            if subitem.type == "function_definition":
                                                method_node = subitem
                                                method_extent_node = item
                                                break

                                    if method_node:
                                        method_name_node = method_node.child_by_field_name(
                                            "name"
                                        )
                                        if method_name_node:
                                            method_name = parser._extract_text(
                                                source_code,
                                                method_name_node.start_byte,
                                                method_name_node.end_byte,
                                            )
                                            if method_name == entity_path.method_name:
                                                entity_node = method_node
                                                entity_extent_node = method_extent_node
                                                break

        elif child.type == "class_definition":
            name_node = child.child_by_field_name("name")
            if name_node:
                name = parser._extract_text(
                    source_code, name_node.start_byte, name_node.end_byte
                )
                if name == entity_path.entity_name:
                    entity_node = child
                    entity_extent_node = child
                    break

                if entity_path.is_method and name == entity_path.class_name:
                    body = child.child_by_field_name("body")
                    if body:
                        for item in body.children:
                            method_node = None
                            method_extent_node = None

                            if item.type == "function_definition":
                                method_node = item
                                method_extent_node = item
                            elif item.type == "decorated_definition":
                                for subitem in item.children:
                                    if subitem.type == "function_definition":
                                        method_node = subitem
                                        method_extent_node = item
                                        break

                            if method_node:
                                method_name_node = method_node.child_by_field_name(
                                    "name"
                                )
                                if method_name_node:
                                    method_name = parser._extract_text(
                                        source_code,
                                        method_name_node.start_byte,
                                        method_name_node.end_byte,
                                    )
                                    if method_name == entity_path.method_name:
                                        entity_node = method_node
                                        entity_extent_node = method_extent_node
                                        break

    if entity_node is None:
        raise ValueError(f"Entity not found in file: {entity_path.entity_name}")

    if entity_node.type == "function_definition":
        computed_hash = compute_function_hash(entity_node, source_code)
        kind = "method" if entity_path.is_method else "function"
    elif entity_node.type == "class_definition":
        computed_hash = compute_class_hash(entity_node, source_code)
        kind = "class"
    else:
        raise ValueError(f"Unsupported entity type: {entity_node.type}")

    current_docstring = parser._extract_docstring(entity_node, source_code)
    if current_docstring:
        current_docstring = current_docstring.strip()
    current_hash = (
        parser.parse_athena_tag(current_docstring) if current_docstring else None
    )

    extent = Location(
        start=entity_extent_node.start_point[0],
        end=entity_extent_node.end_point[0]
    )

    return EntityStatus(
        kind=kind,
        path=entity_path_str,
        extent=extent,
        recorded_hash=current_hash,
        calculated_hash=computed_hash
    )


def sync_entity(entity_path_str: str, force: bool, repo_root: Path) -> bool:
    """Sync hash tag for a single entity.

    Uses inspect_entity() to analyze the entity state, then updates the
    docstring if needed.

    Args:
        entity_path_str: Entity path string (e.g., "src/foo.py:Bar")
        force: Force update even if hash matches
        repo_root: Repository root directory

    Returns:
        True if entity was updated, False otherwise

    Raises:
        FileNotFoundError: If entity file doesn't exist
        ValueError: If entity is not found in file or path is invalid
    """
    status = inspect_entity(entity_path_str, repo_root)

    if not needs_update(status.recorded_hash, status.calculated_hash, force):
        return False

    entity_path = parse_entity_path(entity_path_str)

    # Handle package-level sync
    if entity_path.is_package:
        package_dir = resolve_entity_path(entity_path, repo_root)
        init_file = package_dir / "__init__.py"

        # Read __init__.py (or use empty string if it doesn't exist)
        source_code = init_file.read_text() if init_file.exists() else ""

        # Extract current package docstring
        current_docstring = extract_module_docstring(source_code)
        if current_docstring:
            current_docstring = current_docstring.strip()

        # Update @athena tag in docstring
        parser = PythonParser()
        updated_docstring = parser.update_athena_tag(current_docstring, status.calculated_hash)

        # Update package docstring in __init__.py
        updated_source = update_module_docstring(source_code, updated_docstring)
        init_file.write_text(updated_source)

        return True

    # Handle module-level sync
    if entity_path.is_module:
        resolved_path = resolve_entity_path(entity_path, repo_root)
        source_code = resolved_path.read_text()

        # Extract current module docstring
        current_docstring = extract_module_docstring(source_code)
        if current_docstring:
            current_docstring = current_docstring.strip()

        # Update @athena tag in docstring
        parser = PythonParser()
        updated_docstring = parser.update_athena_tag(current_docstring, status.calculated_hash)

        # Update module docstring in file
        updated_source = update_module_docstring(source_code, updated_docstring)
        resolved_path.write_text(updated_source)

        return True

    resolved_path = resolve_entity_path(entity_path, repo_root)
    source_code = resolved_path.read_text()

    parser = PythonParser()
    tree = parser.parser.parse(bytes(source_code, "utf8"))
    root_node = tree.root_node

    entity_node = None
    entity_extent_node = None

    for child in root_node.children:
        if child.type == "function_definition":
            name_node = child.child_by_field_name("name")
            if name_node:
                name = parser._extract_text(
                    source_code, name_node.start_byte, name_node.end_byte
                )
                if name == entity_path.entity_name:
                    entity_node = child
                    entity_extent_node = child
                    break

        elif child.type == "decorated_definition":
            for subchild in child.children:
                if subchild.type == "function_definition":
                    name_node = subchild.child_by_field_name("name")
                    if name_node:
                        name = parser._extract_text(
                            source_code, name_node.start_byte, name_node.end_byte
                        )
                        if name == entity_path.entity_name:
                            entity_node = subchild
                            entity_extent_node = child
                            break
                elif subchild.type == "class_definition":
                    name_node = subchild.child_by_field_name("name")
                    if name_node:
                        name = parser._extract_text(
                            source_code, name_node.start_byte, name_node.end_byte
                        )
                        if name == entity_path.entity_name:
                            entity_node = subchild
                            entity_extent_node = child
                            break

                        # Check if we're looking for a method within this decorated class
                        if entity_path.is_method and name == entity_path.class_name:
                            body = subchild.child_by_field_name("body")
                            if body:
                                for item in body.children:
                                    method_node = None
                                    method_extent_node = None

                                    if item.type == "function_definition":
                                        method_node = item
                                        method_extent_node = item
                                    elif item.type == "decorated_definition":
                                        for subitem in item.children:
                                            if subitem.type == "function_definition":
                                                method_node = subitem
                                                method_extent_node = item
                                                break

                                    if method_node:
                                        method_name_node = method_node.child_by_field_name(
                                            "name"
                                        )
                                        if method_name_node:
                                            method_name = parser._extract_text(
                                                source_code,
                                                method_name_node.start_byte,
                                                method_name_node.end_byte,
                                            )
                                            if method_name == entity_path.method_name:
                                                entity_node = method_node
                                                entity_extent_node = method_extent_node
                                                break

        elif child.type == "class_definition":
            name_node = child.child_by_field_name("name")
            if name_node:
                name = parser._extract_text(
                    source_code, name_node.start_byte, name_node.end_byte
                )
                if name == entity_path.entity_name:
                    entity_node = child
                    entity_extent_node = child
                    break

                if entity_path.is_method and name == entity_path.class_name:
                    body = child.child_by_field_name("body")
                    if body:
                        for item in body.children:
                            method_node = None
                            method_extent_node = None

                            if item.type == "function_definition":
                                method_node = item
                                method_extent_node = item
                            elif item.type == "decorated_definition":
                                for subitem in item.children:
                                    if subitem.type == "function_definition":
                                        method_node = subitem
                                        method_extent_node = item
                                        break

                            if method_node:
                                method_name_node = method_node.child_by_field_name(
                                    "name"
                                )
                                if method_name_node:
                                    method_name = parser._extract_text(
                                        source_code,
                                        method_name_node.start_byte,
                                        method_name_node.end_byte,
                                    )
                                    if method_name == entity_path.method_name:
                                        entity_node = method_node
                                        entity_extent_node = method_extent_node
                                        break

    current_docstring = parser._extract_docstring(entity_node, source_code)
    if current_docstring:
        current_docstring = current_docstring.strip()

    updated_docstring = parser.update_athena_tag(current_docstring, status.calculated_hash)

    entity_location = Location(
        start=entity_extent_node.start_point[0], end=entity_extent_node.end_point[0]
    )

    updated_source = update_docstring_in_source(
        source_code, entity_location, updated_docstring
    )

    resolved_path.write_text(updated_source)

    return True


def collect_sub_entities(entity_path: EntityPath, repo_root: Path) -> list[str]:
    """Collect all sub-entities for a given entity path.

    For modules: returns all functions, classes, and methods
    For packages: returns all modules and their entities
    For classes: returns all methods

    Args:
        entity_path: Parsed entity path
        repo_root: Repository root directory

    Returns:
        List of entity path strings for all sub-entities
    """
    resolved_path = resolve_entity_path(entity_path, repo_root)
    if resolved_path is None:
        return []

    sub_entities = []
    parser = PythonParser()

    # Handle package (directory with __init__.py)
    if entity_path.is_package:
        # Find all .py files in the package
        for py_file in resolved_path.rglob("*.py"):
            # Skip excluded paths
            if should_exclude_path(py_file, repo_root):
                continue

            # Handle subpackages (nested __init__.py files)
            if py_file.name == "__init__.py":
                # Skip the package's own __init__.py (it's already handled by sync_recursive)
                if py_file.parent == resolved_path:
                    continue

                # This is a subpackage - add it as a package entity
                rel_path = py_file.parent.relative_to(repo_root)
                sub_entities.append(str(rel_path))
                continue

            # Get relative path from repo root
            rel_path = py_file.relative_to(repo_root)

            # Read file and extract entities
            source_code = py_file.read_text()
            entities = parser.extract_entities(source_code, str(rel_path))

            # Add all entities
            for entity in entities:
                if entity.kind == "function":
                    sub_entities.append(f"{rel_path}:{entity.name}")
                elif entity.kind == "class":
                    sub_entities.append(f"{rel_path}:{entity.name}")
                elif entity.kind == "method":
                    # Method names include class prefix
                    sub_entities.append(f"{rel_path}:{entity.name}")

        return sub_entities

    # Handle module (single .py file)
    if entity_path.is_module:
        source_code = resolved_path.read_text()
        entities = parser.extract_entities(source_code, entity_path.file_path)

        for entity in entities:
            if entity.kind == "function":
                sub_entities.append(f"{entity_path.file_path}:{entity.name}")
            elif entity.kind == "class":
                sub_entities.append(f"{entity_path.file_path}:{entity.name}")
            elif entity.kind == "method":
                # Method names include class prefix
                sub_entities.append(f"{entity_path.file_path}:{entity.name}")

        return sub_entities

    # Handle class (return all methods)
    if entity_path.is_class:
        source_code = resolved_path.read_text()
        entities = parser.extract_entities(source_code, entity_path.file_path)

        for entity in entities:
            if entity.kind == "method" and entity.name.startswith(
                f"{entity_path.entity_name}."
            ):
                sub_entities.append(f"{entity_path.file_path}:{entity.name}")

        return sub_entities

    # For methods or functions, no sub-entities
    return []


def sync_recursive(entity_path_str: str, force: bool, repo_root: Path) -> int:
    """Recursively sync an entity and all its sub-entities.

    For modules: syncs the module itself and all functions, classes, and methods
    For packages: syncs the package itself and all modules and their entities
    For classes: syncs the class and all its methods
    For functions/methods: syncs only that entity

    Args:
        entity_path_str: Entity path string
        force: Force update even if hash matches
        repo_root: Repository root directory

    Returns:
        Number of entities updated
    """
    entity_path = parse_entity_path(entity_path_str)

    # Collect all entities to sync (including the main entity if applicable)
    entities_to_sync = []

    # For packages and modules, sync the package/module itself and all sub-entities
    if entity_path.is_package or entity_path.is_module:
        entities_to_sync.append(entity_path_str)
        entities_to_sync.extend(collect_sub_entities(entity_path, repo_root))
    else:
        # For classes, sync the class itself and all methods
        if entity_path.is_class:
            entities_to_sync.append(entity_path_str)
            entities_to_sync.extend(collect_sub_entities(entity_path, repo_root))
        else:
            # For functions/methods, just sync the entity itself
            entities_to_sync.append(entity_path_str)

    # Sync all entities
    update_count = 0
    for entity in entities_to_sync:
        try:
            if sync_entity(entity, force, repo_root):
                update_count += 1
        except (ValueError, FileNotFoundError) as e:
            # Log error but continue with other entities
            # In a real implementation, we might want to use proper logging
            print(f"Warning: Failed to sync {entity}: {e}")

    return update_count
