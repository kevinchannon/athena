"""Hash generation infrastructure for code entities using tree-sitter AST."""

import hashlib
import re


def _is_first_child_of_parent(node, parent_node) -> bool:
    """Check if a node is the first child of its parent.

    Args:
        node: The node to check
        parent_node: The parent node

    Returns:
        True if this is the first child of the parent
    """
    if parent_node is None:
        return False

    if parent_node.type not in ("block", "module"):
        return False

    return parent_node.children and parent_node.children[0] == node


def _is_docstring_node(node, parent_node) -> bool:
    """Check if a node is a docstring (first statement in body that's a string).

    Args:
        node: The node to check
        parent_node: The parent node (should be a block or module)

    Returns:
        True if this is a docstring node
    """
    if node.type != "expression_statement":
        return False

    if not _is_first_child_of_parent(node, parent_node):
        return False

    for child in node.children:
        if child.type == "string":
            return True

    return False


def serialize_ast_node(node, source_code: str) -> str:
    """Serialize a tree-sitter AST node to a stable string representation.

    This serialization includes node types and names, which forms the basis for
    generating content hashes. The serialization is designed to be stable across
    whitespace changes but sensitive to semantic changes.

    Docstrings are excluded from serialization to ensure hash stability when
    @athena tags are added or updated.

    Args:
        node: Tree-sitter AST node to serialize
        source_code: Source code string for extracting identifiers

    Returns:
        Serialized string representation of the AST structure
    """
    parts = []

    def serialize(n, parent=None, depth: int = 0):
        """Recursively serialize the node and its children."""
        # Skip docstring nodes
        if _is_docstring_node(n, parent):
            return

        # For nodes with meaningful text content, include the text
        if n.type in ("identifier", "integer", "float", "string"):
            text = source_code.encode("utf8")[n.start_byte : n.end_byte].decode("utf8")
            parts.append(f"{n.type}:{text}")
        else:
            # Add node type
            parts.append(f"{n.type}")

        # Recursively serialize children
        for child in n.children:
            serialize(child, n, depth + 1)

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


def compute_module_hash(source_code: str) -> str:
    """Compute hash for a module based on complete file AST.

    The hash is calculated from the full AST representation of the module,
    excluding docstrings. This captures all semantically significant content
    including module-level code, imports, and function/class definitions.

    Args:
        source_code: Complete source code of the module

    Returns:
        12-character hex hash
    """
    import tree_sitter_python
    from tree_sitter import Language, Parser

    language = Language(tree_sitter_python.language())
    parser = Parser(language)
    tree = parser.parse(bytes(source_code, "utf8"))

    serialization = serialize_ast_node(tree.root_node, source_code)

    return compute_hash(serialization)


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
