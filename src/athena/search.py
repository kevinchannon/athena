"""FTS5-based docstring search for code navigation.

This module provides efficient docstring-based search functionality using SQLite
FTS5 (Full-Text Search) with SQLite-based caching. FTS5 uses BM25 ranking internally
to score search results.
"""

import logging
import os
import sqlite3
from pathlib import Path

from athena.cache import CacheDatabase, CachedEntity
from athena.config import SearchConfig, load_search_config
from athena.models import Location, SearchResult
from athena.parsers.python_parser import PythonParser
from athena.repository import find_python_files, find_repository_root

logger = logging.getLogger(__name__)


def _parse_module_docstring(
    parser: PythonParser,
    root_node,
    source_code: str,
    relative_path: str
) -> list[tuple[str, str, Location, str]]:
    """Extract module-level docstring if present.

    Args:
        parser: PythonParser instance for docstring extraction.
        root_node: Root AST node of the module.
        source_code: The source code content.
        relative_path: Path relative to repository root (as POSIX string).

    Returns:
        List with single module entity tuple, or empty list if no module docstring.
    """
    module_docstring = parser._extract_docstring(root_node, source_code)
    if not module_docstring:
        return []

    lines = source_code.splitlines()
    extent = Location(start=0, end=len(lines) - 1 if lines else 0)
    return [("module", relative_path, extent, module_docstring)]


def _extract_entity_with_docstring(
    parser: PythonParser,
    definition_node,
    extent_node,
    source_code: str,
    relative_path: str,
    kind: str
) -> list[tuple[str, str, Location, str]]:
    """Extract a single entity (function/class/method) if it has a docstring.

    Args:
        parser: PythonParser instance for docstring extraction.
        definition_node: AST node containing the definition (function_definition/class_definition).
        extent_node: AST node defining the extent (may include decorators).
        source_code: The source code content.
        relative_path: Path relative to repository root (as POSIX string).
        kind: Entity kind ("function", "class", or "method").

    Returns:
        List with single entity tuple if docstring exists, empty list otherwise.
    """
    docstring = parser._extract_docstring(definition_node, source_code)
    if not docstring:
        return []

    start_line = extent_node.start_point[0]
    end_line = extent_node.end_point[0]
    extent = Location(start=start_line, end=end_line)
    return [(kind, relative_path, extent, docstring)]


def _parse_class_methods(
    parser: PythonParser,
    class_node,
    source_code: str,
    relative_path: str
) -> list[tuple[str, str, Location, str]]:
    """Extract methods with docstrings from a class body.

    Args:
        parser: PythonParser instance for docstring extraction.
        class_node: AST node for the class definition.
        source_code: The source code content.
        relative_path: Path relative to repository root (as POSIX string).

    Returns:
        List of method entity tuples with docstrings.
    """
    methods = []
    body = class_node.child_by_field_name("body")
    if not body:
        return methods

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
            methods.extend(_extract_entity_with_docstring(
                parser, method_node, method_extent_node, source_code, relative_path, "method"
            ))

    return methods


def _parse_file_entities(file_path: Path, source_code: str, relative_path: str) -> list[tuple[str, str, Location, str]]:
    """Parse entities with docstrings from a single Python file.

    Args:
        file_path: Path to the Python file.
        source_code: The source code content of the file.
        relative_path: Path relative to repository root (as POSIX string).

    Returns:
        List of (kind, path, extent, docstring) tuples for entities with docstrings.
        Empty list if no entities with docstrings found.
    """
    parser = PythonParser()
    entities_with_docs = []

    tree = parser.parser.parse(bytes(source_code, "utf8"))
    root_node = tree.root_node

    entities_with_docs.extend(_parse_module_docstring(parser, root_node, source_code, relative_path))

    for child in root_node.children:
        func_node = None
        class_node = None
        extent_node = None

        if child.type == "function_definition":
            func_node = child
            extent_node = child
        elif child.type == "decorated_definition":
            for subchild in child.children:
                if subchild.type == "function_definition":
                    func_node = subchild
                    extent_node = child
                elif subchild.type == "class_definition":
                    class_node = subchild
                    extent_node = child
        elif child.type == "class_definition":
            class_node = child
            extent_node = child

        if func_node:
            name_node = func_node.child_by_field_name("name")
            if name_node:
                entities_with_docs.extend(_extract_entity_with_docstring(
                    parser, func_node, extent_node, source_code, relative_path, "function"
                ))

        if class_node:
            entities_with_docs.extend(_extract_entity_with_docstring(
                parser, class_node, extent_node, source_code, relative_path, "class"
            ))
            entities_with_docs.extend(_parse_class_methods(
                parser, class_node, source_code, relative_path
            ))

    return entities_with_docs


def _process_file_with_cache(
    cache_db: CacheDatabase,
    file_path: Path,
    current_mtime: float,
    root: Path
) -> list[tuple[str, str, Location, str]]:
    """Process a file with cache awareness.

    Checks if the file is in cache and up-to-date. If not, parses the file
    and updates the cache. Returns the entities for the file.

    Args:
        cache_db: The cache database instance.
        file_path: Absolute path to the Python file.
        current_mtime: Current modification time of the file.
        root: Repository root for computing relative path.

    Returns:
        List of (kind, path, extent, docstring) tuples for entities with docstrings.
    """
    relative_path = file_path.relative_to(root).as_posix()

    # Check if file exists in cache
    cached_file = cache_db.get_file(relative_path)

    if cached_file is None:
        try:
            source_code = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []

        entities = _parse_file_entities(file_path, source_code, relative_path)

        # Group file and entity insertion in a single transaction
        try:
            with cache_db.transaction():
                file_id = cache_db.insert_file(relative_path, current_mtime)
                cached_entities = [
                    CachedEntity(
                        file_id=file_id,
                        kind=kind,
                        name=relative_path,  # Using path as name for now
                        entity_path=path,
                        start=extent.start,
                        end=extent.end,
                        summary=docstring
                    )
                    for kind, path, extent, docstring in entities
                ]
                cache_db.insert_entities(file_id, cached_entities)
        except sqlite3.IntegrityError:
            # File was inserted by another thread - this is fine in concurrent scenarios
            # Return empty list since entities are already cached
            pass

        return entities

    file_id, cached_mtime = cached_file

    if current_mtime != cached_mtime:
        try:
            source_code = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []

        entities = _parse_file_entities(file_path, source_code, relative_path)

        # Group related operations in a single transaction for atomicity
        with cache_db.transaction():
            cache_db.delete_entities_for_file(file_id)
            cached_entities = [
                CachedEntity(
                    file_id=file_id,
                    kind=kind,
                    name=relative_path,
                    entity_path=path,
                    start=extent.start,
                    end=extent.end,
                    summary=docstring
                )
                for kind, path, extent, docstring in entities
            ]
            cache_db.insert_entities(file_id, cached_entities)
            cache_db.update_file_mtime(file_id, current_mtime)

        return entities

    # File is up-to-date in cache - no need to parse
    # We don't return cached entities here since we'll load all entities
    # at once in the next phase for FTS5 search
    return []


def _scan_repo_with_cache(root: Path, cache_db: CacheDatabase) -> list[tuple[str, str, Location, str]]:
    """Scan repository and update cache with all entities.

    Scans all Python files in the repository, processes them with cache awareness,
    and removes stale entries for deleted files.

    Args:
        root: Repository root directory.
        cache_db: The cache database instance.

    Returns:
        List of (kind, path, extent, docstring) tuples for all entities with docstrings.

    Raises:
        sqlite3.Error: If database operations fail.
    """
    seen_files = []

    # Scan all Python files and process with cache
    for py_file in find_python_files(root):
        try:
            current_mtime = os.path.getmtime(py_file)
        except OSError:
            # Skip files we can't stat
            continue

        relative_path = py_file.relative_to(root).as_posix()
        seen_files.append(relative_path)

        # Process file with cache (updates cache if needed)
        _process_file_with_cache(cache_db, py_file, current_mtime, root)

    # Clean up deleted files from cache
    cache_db.delete_files_not_in(seen_files)

    # Return all entities from cache
    all_entities = cache_db.get_all_entities()
    return [
        (kind, path, Location(start=start, end=end), summary)
        for kind, path, start, end, summary in all_entities
    ]




def search_docstrings(
    query: str,
    root: Path | None = None,
    config: SearchConfig | None = None
) -> list[SearchResult]:
    """Search docstrings using FTS5 with two-tier strategy and return top-k results.

    Uses a two-tier search approach:
    1. Tier 1: Exact phrase matches (highest priority)
    2. Tier 2: Standard FTS5 matches (if needed to fill max_results)

    Args:
        query: Natural language search query.
        root: Repository root directory. If None, attempts to find it.
        config: Search configuration. If None, loads from .athena file.

    Returns:
        List of SearchResult objects sorted by relevance (phrase matches first, then FTS5 scored).
        Returns empty list if query is empty or no matches found.

    Raises:
        RepositoryNotFoundError: If root is None and no repository found.
        sqlite3.Error: If cache operations fail.

    Examples:
        >>> results = search_docstrings("JWT authentication")
        >>> for result in results:
        ...     print(f"{result.kind}: {result.path}:{result.extent.start}")
    """
    if not query:
        return []

    # Find or validate repository root
    if root is None:
        root = find_repository_root()
    else:
        # Validate that provided root is a git repository
        root = find_repository_root(root)

    # Load configuration if not provided
    if config is None:
        config = load_search_config(root)

    # Scan repository to update cache
    cache_dir = root / ".athena-cache"
    with CacheDatabase(cache_dir) as cache_db:
        _scan_repo_with_cache(root, cache_db)

        # Tier 1: Exact phrase match
        phrase_ids = cache_db.query_phrase(query, config.max_results)

        # Tier 2: Standard FTS5 if needed
        remaining = config.max_results - len(phrase_ids)
        if remaining > 0:
            standard_ids = cache_db.query_words(
                query, remaining, exclude_ids=set(phrase_ids)
            )
            all_ids = phrase_ids + standard_ids
        else:
            all_ids = phrase_ids[:config.max_results]

        # Convert entity IDs to SearchResult objects
        search_results = []
        for entity_id in all_ids:
            entity = cache_db.get_entity_by_id(entity_id)
            if entity:
                kind, path, start, end, summary = entity
                search_results.append(
                    SearchResult(
                        kind=kind,
                        path=path,
                        extent=Location(start=start, end=end),
                        summary=summary
                    )
                )

    return search_results
