"""Hash generation infrastructure for code entities using tree-sitter AST."""

import hashlib
import re


def serialize_ast_node(node, source_code: str) -> str:
    """Serialize a tree-sitter AST node to a stable string representation.

    This serialization includes node types and names, which forms the basis for
    generating content hashes. The serialization is designed to be stable across
    whitespace changes but sensitive to semantic changes.

    Args:
        node: Tree-sitter AST node to serialize
        source_code: Source code string for extracting identifiers

    Returns:
        Serialized string representation of the AST structure
    """
    parts = []

    def serialize(n, depth: int = 0):
        """Recursively serialize the node and its children."""
        # Add node type
        parts.append(f"{n.type}")

        # For identifier nodes, include the actual name
        if n.type == "identifier":
            text = source_code.encode("utf8")[n.start_byte : n.end_byte].decode("utf8")
            parts.append(f":{text}")

        # Recursively serialize children
        for child in n.children:
            serialize(child, depth + 1)

    serialize(node)
    return "|".join(parts)


def compute_hash(content: str) -> str:
    """Compute SHA-256 hash and truncate to 12 hex characters.

    Args:
        content: Content string to hash

    Returns:
        12-character hex hash string
    """
    hash_obj = hashlib.sha256(content.encode("utf8"))
    return hash_obj.hexdigest()[:12]


def compute_function_hash(node, source_code: str) -> str:
    """Compute hash for a function (signature + body).

    Args:
        node: Tree-sitter function_definition node
        source_code: Source code string

    Returns:
        12-character hex hash
    """
    # Serialize the entire function node (includes signature and body)
    serialization = serialize_ast_node(node, source_code)
    return compute_hash(serialization)


def compute_class_hash(node, source_code: str) -> str:
    """Compute hash for a class (declaration + method signatures + implementations).

    Args:
        node: Tree-sitter class_definition node
        source_code: Source code string

    Returns:
        12-character hex hash
    """
    # Serialize the entire class node (includes declaration, methods, etc.)
    serialization = serialize_ast_node(node, source_code)
    return compute_hash(serialization)


def compute_module_hash(entities_docstrings: list[str]) -> str:
    """Compute hash for a module based on non-whitespace from entity docstrings.

    Args:
        entities_docstrings: List of docstring contents from module entities

    Returns:
        12-character hex hash
    """
    # Concatenate all docstrings with non-whitespace characters only
    combined = ""
    for docstring in entities_docstrings:
        if docstring:
            # Remove all whitespace
            no_whitespace = re.sub(r"\s+", "", docstring)
            combined += no_whitespace

    return compute_hash(combined)


def compute_package_hash(module_docstrings: list[str]) -> str:
    """Compute hash for a package based on non-whitespace from module docstrings.

    Args:
        module_docstrings: List of module docstrings from package

    Returns:
        12-character hex hash
    """
    # Same logic as module hash - concatenate non-whitespace
    combined = ""
    for docstring in module_docstrings:
        if docstring:
            # Remove all whitespace
            no_whitespace = re.sub(r"\s+", "", docstring)
            combined += no_whitespace

    return compute_hash(combined)
