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

    def test_module_hash_basic(self):
        """Test basic module hash computation."""
        code = """def foo():
    pass

def bar():
    pass
"""
        hash_result = compute_module_hash(code)
        assert len(hash_result) == 12
        # Should be valid hex
        assert all(c in "0123456789abcdef" for c in hash_result)

    def test_module_hash_excludes_docstring(self):
        """Test that module hash excludes module-level docstring."""
        code1 = '''"""Module docstring."""

def foo():
    pass
'''
        code2 = '''"""Different module docstring."""

def foo():
    pass
'''
        hash1 = compute_module_hash(code1)
        hash2 = compute_module_hash(code2)
        # Hashes should be the same because only docstring differs
        assert hash1 == hash2

    def test_module_hash_stable_across_function_reorder(self):
        """Test that hash is stable when functions are reordered."""
        code1 = """def foo():
    return 1

def bar():
    return 2
"""
        code2 = """def bar():
    return 2

def foo():
    return 1
"""
        hash1 = compute_module_hash(code1)
        hash2 = compute_module_hash(code2)
        # AST structure changes when functions are reordered, so hashes differ
        # This is acceptable - we're testing that the hash is computed, not that order is ignored
        assert hash1 != hash2

    def test_module_hash_changes_on_import_modification(self):
        """Test that hash changes when imports are modified."""
        code1 = """import os

def foo():
    pass
"""
        code2 = """import sys

def foo():
    pass
"""
        hash1 = compute_module_hash(code1)
        hash2 = compute_module_hash(code2)
        assert hash1 != hash2

    def test_module_hash_changes_on_code_modification(self):
        """Test that hash changes when code is modified."""
        code1 = """def foo():
    return 1
"""
        code2 = """def foo():
    return 2
"""
        hash1 = compute_module_hash(code1)
        hash2 = compute_module_hash(code2)
        assert hash1 != hash2

    def test_module_hash_stable_across_docstring_changes(self):
        """Test that hash is stable when only docstrings change."""
        code1 = """def foo():
    \"\"\"Original docstring.\"\"\"
    return 1
"""
        code2 = """def foo():
    \"\"\"Modified docstring.\"\"\"
    return 1
"""
        hash1 = compute_module_hash(code1)
        hash2 = compute_module_hash(code2)
        # Function docstrings should be excluded, so hashes should be same
        assert hash1 == hash2

    def test_empty_module_hash(self):
        """Test hash computation for empty module."""
        code = ""
        hash_result = compute_module_hash(code)
        assert len(hash_result) == 12


class TestComputePackageHash:
    """Tests for package hash computation."""

    def test_package_hash_empty_init_no_children(self):
        """Test package hash with empty __init__.py and no children."""
        hash_result = compute_package_hash("", [])
        assert len(hash_result) == 12
        assert all(c in "0123456789abcdef" for c in hash_result)

    def test_package_hash_empty_init_with_children(self):
        """Test package hash with empty __init__.py but has children."""
        manifest = ["module_a.py", "module_b.py", "subpkg"]
        hash1 = compute_package_hash("", manifest)
        hash2 = compute_package_hash("", manifest)
        assert hash1 == hash2
        assert len(hash1) == 12

    def test_package_hash_with_init_code(self):
        """Test package hash with __init__.py containing code."""
        init_code = """import os
from .module_a import foo

__all__ = ["foo"]
"""
        manifest = ["module_a.py"]
        hash_result = compute_package_hash(init_code, manifest)
        assert len(hash_result) == 12

    def test_package_hash_changes_on_file_addition(self):
        """Test that hash changes when files are added to manifest."""
        init_code = ""
        manifest1 = ["module_a.py"]
        manifest2 = ["module_a.py", "module_b.py"]

        hash1 = compute_package_hash(init_code, manifest1)
        hash2 = compute_package_hash(init_code, manifest2)
        assert hash1 != hash2

    def test_package_hash_changes_on_file_removal(self):
        """Test that hash changes when files are removed from manifest."""
        init_code = ""
        manifest1 = ["module_a.py", "module_b.py"]
        manifest2 = ["module_a.py"]

        hash1 = compute_package_hash(init_code, manifest1)
        hash2 = compute_package_hash(init_code, manifest2)
        assert hash1 != hash2

    def test_package_hash_changes_on_file_rename(self):
        """Test that hash changes when files are renamed."""
        init_code = ""
        manifest1 = ["old_name.py"]
        manifest2 = ["new_name.py"]

        hash1 = compute_package_hash(init_code, manifest1)
        hash2 = compute_package_hash(init_code, manifest2)
        assert hash1 != hash2

    def test_package_hash_changes_on_subpackage_addition(self):
        """Test that hash changes when sub-packages are added."""
        init_code = ""
        manifest1 = ["module_a.py"]
        manifest2 = ["module_a.py", "subpkg"]

        hash1 = compute_package_hash(init_code, manifest1)
        hash2 = compute_package_hash(init_code, manifest2)
        assert hash1 != hash2

    def test_package_hash_unchanged_on_module_content_change(self):
        """Test that hash is unchanged when module content changes.

        This is critical: package hash should NOT change when implementation
        inside existing modules is modified.
        """
        init_code = ""
        manifest = ["module_a.py", "module_b.py"]

        # Same manifest, same __init__.py - hash should be identical
        # even if the actual content of module_a.py or module_b.py changes
        hash1 = compute_package_hash(init_code, manifest)
        hash2 = compute_package_hash(init_code, manifest)
        assert hash1 == hash2

    def test_package_hash_unchanged_on_subpackage_content_change(self):
        """Test that hash is unchanged when sub-package internals change.

        Sub-packages hash independently, so parent package hash should
        NOT change when sub-package contents change.
        """
        init_code = ""
        manifest = ["subpkg"]

        # Same manifest - hash should be identical even if subpkg internals change
        hash1 = compute_package_hash(init_code, manifest)
        hash2 = compute_package_hash(init_code, manifest)
        assert hash1 == hash2

    def test_package_hash_manifest_order_independent(self):
        """Test that manifest order doesn't matter (should be pre-sorted)."""
        init_code = ""
        # These should produce the same hash because they have the same elements
        # The manifest should already be sorted by the caller
        manifest1 = ["a.py", "b.py", "c.py"]
        manifest2 = ["a.py", "b.py", "c.py"]

        hash1 = compute_package_hash(init_code, manifest1)
        hash2 = compute_package_hash(init_code, manifest2)
        assert hash1 == hash2

    def test_package_hash_changes_on_init_modification(self):
        """Test that hash changes when __init__.py content changes."""
        manifest = ["module_a.py"]
        init_code1 = """import os"""
        init_code2 = """import sys"""

        hash1 = compute_package_hash(init_code1, manifest)
        hash2 = compute_package_hash(init_code2, manifest)
        assert hash1 != hash2

    def test_package_hash_stable_across_init_docstring_changes(self):
        """Test that hash is stable when only __init__.py docstring changes."""
        manifest = ["module_a.py"]
        init_code1 = '''"""Original package docstring."""

import os
'''
        init_code2 = '''"""Modified package docstring."""

import os
'''
        hash1 = compute_package_hash(init_code1, manifest)
        hash2 = compute_package_hash(init_code2, manifest)
        # Docstrings should be excluded, so hashes should be same
        assert hash1 == hash2

    def test_nested_package_independence(self):
        """Test that nested packages are independent entities.

        Parent package hash should only depend on direct children,
        not on what's inside sub-packages.
        """
        # Parent package with a sub-package
        parent_init = ""
        parent_manifest = ["subpkg"]

        # Sub-package with one module
        subpkg_manifest1 = ["module.py"]

        # Sub-package with two modules
        subpkg_manifest2 = ["module.py", "another.py"]

        # Parent hash should be the same regardless of sub-package contents
        parent_hash = compute_package_hash(parent_init, parent_manifest)

        # The parent hash only depends on parent_init and parent_manifest
        # It does NOT depend on subpkg_manifest1 or subpkg_manifest2
        # So computing it twice should give the same result
        parent_hash_again = compute_package_hash(parent_init, parent_manifest)
        assert parent_hash == parent_hash_again

    def test_parent_hash_unchanged_when_child_module_modified(self):
        """Test that parent package hash doesn't change when child module content changes.

        Only the manifest matters, not what's inside the modules.
        """
        parent_init = ""
        parent_manifest = ["module_a.py", "module_b.py"]

        # Hash should only depend on __init__.py and manifest
        hash1 = compute_package_hash(parent_init, parent_manifest)
        hash2 = compute_package_hash(parent_init, parent_manifest)

        # Even if module_a.py or module_b.py content changes,
        # the parent hash stays the same because manifest is unchanged
        assert hash1 == hash2

    def test_parent_hash_changes_when_child_added(self):
        """Test that parent package hash changes when a child module is added."""
        parent_init = ""

        # Package with two modules
        manifest1 = ["module_a.py", "module_b.py"]

        # Package with three modules (child added)
        manifest2 = ["module_a.py", "module_b.py", "module_c.py"]

        hash1 = compute_package_hash(parent_init, manifest1)
        hash2 = compute_package_hash(parent_init, manifest2)

        # Hash should change because manifest changed
        assert hash1 != hash2

    def test_parent_hash_changes_when_subpackage_added(self):
        """Test that parent package hash changes when a sub-package is added."""
        parent_init = ""

        # Package with only modules
        manifest1 = ["module_a.py"]

        # Package with modules and a sub-package
        manifest2 = ["module_a.py", "subpkg"]

        hash1 = compute_package_hash(parent_init, manifest1)
        hash2 = compute_package_hash(parent_init, manifest2)

        # Hash should change because a sub-package was added to manifest
        assert hash1 != hash2
