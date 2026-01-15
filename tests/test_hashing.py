"""Tests for hashing module."""

import pytest
import tree_sitter_python
from tree_sitter import Language, Parser

from athena.hashing import (
    compute_class_hash,
    compute_function_hash,
    compute_hash,
    compute_module_hash,
    compute_package_hash,
    serialize_ast_node,
)


@pytest.fixture
def parser():
    """Create a tree-sitter parser for Python."""
    language = Language(tree_sitter_python.language())
    p = Parser(language)
    return p


def parse_function(parser, code: str):
    """Parse code and return the first function_definition node."""
    tree = parser.parse(bytes(code, "utf8"))
    for node in tree.root_node.children:
        if node.type == "function_definition":
            return node
        # Handle decorated functions
        if node.type == "decorated_definition":
            for child in node.children:
                if child.type == "function_definition":
                    return child
    return None


def parse_class(parser, code: str):
    """Parse code and return the first class_definition node."""
    tree = parser.parse(bytes(code, "utf8"))
    for node in tree.root_node.children:
        if node.type == "class_definition":
            return node
        # Handle decorated classes
        if node.type == "decorated_definition":
            for child in node.children:
                if child.type == "class_definition":
                    return child
    return None


class TestSerializeAstNode:
    """Tests for AST serialization."""

    def test_serialize_simple_function(self, parser):
        """Test serialization of a simple function produces consistent output."""
        code = """def foo():
    pass
"""
        node = parse_function(parser, code)
        result = serialize_ast_node(node, code)
        # Should include function_definition, identifier for name, etc.
        assert "function_definition" in result
        assert "identifier:foo" in result

    def test_serialize_identical_code_produces_same_output(self, parser):
        """Test that identical code produces identical serialization."""
        code1 = """def foo(x):
    return x + 1
"""
        code2 = """def foo(x):
    return x + 1
"""
        node1 = parse_function(parser, code1)
        node2 = parse_function(parser, code2)

        result1 = serialize_ast_node(node1, code1)
        result2 = serialize_ast_node(node2, code2)

        assert result1 == result2

    def test_serialize_whitespace_variations(self, parser):
        """Test that different whitespace produces same serialization."""
        code1 = """def foo(x):
    return x
"""
        code2 = """def foo(x):


    return x
"""
        node1 = parse_function(parser, code1)
        node2 = parse_function(parser, code2)

        result1 = serialize_ast_node(node1, code1)
        result2 = serialize_ast_node(node2, code2)

        # AST structure should be the same despite whitespace differences
        assert result1 == result2

    def test_serialize_different_functions(self, parser):
        """Test that different functions produce different serializations."""
        code1 = """def foo():
    return 1
"""
        code2 = """def bar():
    return 2
"""
        node1 = parse_function(parser, code1)
        node2 = parse_function(parser, code2)

        result1 = serialize_ast_node(node1, code1)
        result2 = serialize_ast_node(node2, code2)

        # Different function names and bodies should produce different serializations
        assert result1 != result2


class TestComputeHash:
    """Tests for hash computation."""

    def test_hash_length(self):
        """Test that hash is truncated to 12 hex characters."""
        result = compute_hash("test content")
        assert len(result) == 12
        # Should be valid hex
        assert all(c in "0123456789abcdef" for c in result)

    def test_hash_stability(self):
        """Test that same input produces same hash."""
        content = "test content for hashing"
        hash1 = compute_hash(content)
        hash2 = compute_hash(content)
        assert hash1 == hash2

    def test_hash_different_for_different_input(self):
        """Test that different inputs produce different hashes."""
        hash1 = compute_hash("content 1")
        hash2 = compute_hash("content 2")
        assert hash1 != hash2


class TestComputeFunctionHash:
    """Tests for function hash computation."""

    def test_function_hash_stability(self, parser):
        """Test that same function produces same hash."""
        code = """def foo(x: int) -> int:
    return x + 1
"""
        node = parse_function(parser, code)
        hash1 = compute_function_hash(node, code)
        hash2 = compute_function_hash(node, code)
        assert hash1 == hash2
        assert len(hash1) == 12

    def test_function_hash_changes_with_signature(self, parser):
        """Test that hash changes when signature changes."""
        code1 = """def foo(x: int) -> int:
    return x
"""
        code2 = """def foo(x: str) -> str:
    return x
"""
        node1 = parse_function(parser, code1)
        node2 = parse_function(parser, code2)

        hash1 = compute_function_hash(node1, code1)
        hash2 = compute_function_hash(node2, code2)

        assert hash1 != hash2

    def test_function_hash_changes_with_body(self, parser):
        """Test that hash changes when body changes."""
        code1 = """def foo(x):
    return x + 1
"""
        code2 = """def foo(x):
    return x + 2
"""
        node1 = parse_function(parser, code1)
        node2 = parse_function(parser, code2)

        hash1 = compute_function_hash(node1, code1)
        hash2 = compute_function_hash(node2, code2)

        assert hash1 != hash2

    def test_function_hash_with_decorator(self, parser):
        """Test hash computation for decorated function."""
        code = """@decorator
def foo():
    pass
"""
        node = parse_function(parser, code)
        hash_result = compute_function_hash(node, code)
        assert len(hash_result) == 12

    def test_function_hash_empty_function(self, parser):
        """Test hash computation for empty function."""
        code = """def foo():
    pass
"""
        node = parse_function(parser, code)
        hash_result = compute_function_hash(node, code)
        assert len(hash_result) == 12

    def test_function_hash_with_type_annotations(self, parser):
        """Test hash computation with complex type annotations."""
        code = """def foo(x: list[int], y: dict[str, Any]) -> tuple[int, str]:
    return (1, "test")
"""
        node = parse_function(parser, code)
        hash_result = compute_function_hash(node, code)
        assert len(hash_result) == 12


class TestComputeClassHash:
    """Tests for class hash computation."""

    def test_class_hash_stability(self, parser):
        """Test that same class produces same hash."""
        code = """class Foo:
    def bar(self):
        pass
"""
        node = parse_class(parser, code)
        hash1 = compute_class_hash(node, code)
        hash2 = compute_class_hash(node, code)
        assert hash1 == hash2
        assert len(hash1) == 12

    def test_class_hash_changes_with_method(self, parser):
        """Test that hash changes when methods change."""
        code1 = """class Foo:
    def bar(self):
        return 1
"""
        code2 = """class Foo:
    def bar(self):
        return 2
"""
        node1 = parse_class(parser, code1)
        node2 = parse_class(parser, code2)

        hash1 = compute_class_hash(node1, code1)
        hash2 = compute_class_hash(node2, code2)

        assert hash1 != hash2

    def test_class_hash_changes_with_new_method(self, parser):
        """Test that hash changes when new method is added."""
        code1 = """class Foo:
    def bar(self):
        pass
"""
        code2 = """class Foo:
    def bar(self):
        pass

    def baz(self):
        pass
"""
        node1 = parse_class(parser, code1)
        node2 = parse_class(parser, code2)

        hash1 = compute_class_hash(node1, code1)
        hash2 = compute_class_hash(node2, code2)

        assert hash1 != hash2

    def test_class_hash_with_inheritance(self, parser):
        """Test hash computation for class with inheritance."""
        code = """class Foo(Base):
    def bar(self):
        pass
"""
        node = parse_class(parser, code)
        hash_result = compute_class_hash(node, code)
        assert len(hash_result) == 12


class TestComputeModuleHash:
    """Tests for module hash computation."""

    def test_module_hash_from_docstrings(self):
        """Test module hash computed from entity docstrings."""
        docstrings = [
            "First function docstring",
            "Second function docstring",
            "A class docstring",
        ]
        hash_result = compute_module_hash(docstrings)
        assert len(hash_result) == 12

    def test_module_hash_stability(self):
        """Test that same docstrings produce same hash."""
        docstrings = ["Doc 1", "Doc 2"]
        hash1 = compute_module_hash(docstrings)
        hash2 = compute_module_hash(docstrings)
        assert hash1 == hash2

    def test_module_hash_ignores_whitespace(self):
        """Test that whitespace in docstrings is ignored."""
        docstrings1 = ["Doc with spaces", "Another   doc"]
        docstrings2 = ["Docwithspaces", "Anotherdoc"]
        hash1 = compute_module_hash(docstrings1)
        hash2 = compute_module_hash(docstrings2)
        assert hash1 == hash2

    def test_module_hash_empty_docstrings(self):
        """Test module hash with empty docstrings."""
        docstrings = []
        hash_result = compute_module_hash(docstrings)
        assert len(hash_result) == 12

    def test_module_hash_none_docstrings(self):
        """Test module hash with None values in list."""
        docstrings = ["Doc 1", None, "Doc 2"]
        hash_result = compute_module_hash(docstrings)
        assert len(hash_result) == 12


class TestComputePackageHash:
    """Tests for package hash computation."""

    def test_package_hash_from_module_docstrings(self):
        """Test package hash computed from module docstrings."""
        module_docstrings = [
            "Module 1 docstring",
            "Module 2 docstring",
        ]
        hash_result = compute_package_hash(module_docstrings)
        assert len(hash_result) == 12

    def test_package_hash_stability(self):
        """Test that same module docstrings produce same hash."""
        docstrings = ["Module doc 1", "Module doc 2"]
        hash1 = compute_package_hash(docstrings)
        hash2 = compute_package_hash(docstrings)
        assert hash1 == hash2

    def test_package_hash_ignores_whitespace(self):
        """Test that whitespace is ignored."""
        docstrings1 = ["Module with   spaces"]
        docstrings2 = ["Modulewithspaces"]
        hash1 = compute_package_hash(docstrings1)
        hash2 = compute_package_hash(docstrings2)
        assert hash1 == hash2
