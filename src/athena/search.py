"""BM25-based docstring search for code navigation.

This module provides efficient docstring-based search functionality using BM25
ranking algorithm with code-aware tokenization and in-memory caching.
"""

import functools
import os
from pathlib import Path

from athena.bm25_searcher import BM25Searcher
from athena.config import SearchConfig, load_search_config
from athena.models import Location, SearchResult
from athena.parsers.python_parser import PythonParser
from athena.repository import find_python_files, find_repository_root


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


def _get_cache_key(root: Path) -> tuple[str, float]:
    """Generate cache key based on repository root and modification time.

    Args:
        root: Repository root directory.

    Returns:
        Tuple of (root_path_string, max_modification_time).
    """
    root_str = str(root)
    max_mtime = 0.0

    # Find the latest modification time across all Python files
    for py_file in find_python_files(root):
        try:
            mtime = os.path.getmtime(py_file)
            max_mtime = max(max_mtime, mtime)
        except OSError:
            # If we can't get mtime, invalidate cache by using current time
            return (root_str, float("inf"))

    return (root_str, max_mtime)


@functools.lru_cache(maxsize=8)
def _extract_entities_with_docstrings(cache_key: tuple[str, float]) -> list[tuple[str, str, Location, str]]:
    """Extract all entities with docstrings from repository (cached).

    This function is cached based on repository root and modification time.
    Cache invalidates when any Python file in the repository changes.

    Args:
        cache_key: Tuple of (root_path_string, max_modification_time).

    Returns:
        List of (kind, path, extent, docstring) tuples for entities with docstrings.
    """
    root = Path(cache_key[0])
    entities_with_docs = []

    for py_file in find_python_files(root):
        try:
            source_code = py_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            # Skip files that can't be read
            continue

        # Get relative path
        relative_path = py_file.relative_to(root).as_posix()

        # Parse file and collect entities
        file_entities = _parse_file_entities(py_file, source_code, relative_path)
        entities_with_docs.extend(file_entities)

    return entities_with_docs


def search_docstrings(
    query: str,
    root: Path | None = None,
    config: SearchConfig | None = None
) -> list[SearchResult]:
    """Search docstrings using BM25 ranking and return top-k results.

    Args:
        query: Natural language search query.
        root: Repository root directory. If None, attempts to find it.
        config: Search configuration. If None, loads from .athena file.

    Returns:
        List of SearchResult objects sorted by relevance (BM25 score descending).
        Returns empty list if query is empty or no matches found.

    Raises:
        RepositoryNotFoundError: If root is None and no repository found.

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

    # Get cached entities with docstrings
    cache_key = _get_cache_key(root)
    entities_with_docs = _extract_entities_with_docstrings(cache_key)

    if not entities_with_docs:
        return []

    # Build corpus and metadata
    docstrings = [doc for _, _, _, doc in entities_with_docs]
    metadata = [(kind, path, extent) for kind, path, extent, _ in entities_with_docs]

    # Perform BM25 search
    searcher = BM25Searcher(docstrings, k1=config.k1, b=config.b)
    results = searcher.search(query.lower(), k=config.k)

    # Filter out zero-score results (no actual matches)
    # BM25 returns score 0 when none of the query terms appear in the document
    filtered_results = [(idx, score) for idx, score in results if score > 0]

    # Convert to SearchResult objects
    search_results = []
    for idx, _score in filtered_results:
        kind, path, extent = metadata[idx]
        docstring = docstrings[idx]
        search_results.append(
            SearchResult(kind=kind, path=path, extent=extent, summary=docstring)
        )

    return search_results
