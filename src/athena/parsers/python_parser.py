import tree_sitter_python
from tree_sitter import Language, Parser

from athena.models import Entity, Location
from athena.parsers.base import BaseParser


class PythonParser(BaseParser):
    """Parser for extracting entities from Python source code using tree-sitter."""

    def __init__(self):
        self.language = Language(tree_sitter_python.language())
        self.parser = Parser(self.language)

    def extract_entities(self, source_code: str, file_path: str) -> list[Entity]:
        """Extract functions, classes, and methods from Python source code.

        Args:
            source_code: Python source code to parse
            file_path: Relative path to the file

        Returns:
            List of Entity objects
        """
        tree = self.parser.parse(bytes(source_code, "utf8"))
        entities = []

        entities.extend(self._extract_functions(tree.root_node, source_code, file_path))
        entities.extend(self._extract_classes(tree.root_node, source_code, file_path))
        entities.extend(self._extract_methods(tree.root_node, source_code, file_path))

        return entities

    def _extract_functions(self, node, source_code: str, file_path: str) -> list[Entity]:
        """Extract top-level function definitions."""
        functions = []
        lines = source_code.splitlines()

        for child in node.children:
            if child.type == "function_definition":
                name_node = child.child_by_field_name("name")
                if name_node:
                    name = source_code[name_node.start_byte:name_node.end_byte]
                    start_line = child.start_point[0]
                    end_line = child.end_point[0]

                    functions.append(Entity(
                        kind="function",
                        path=file_path,
                        extent=Location(start=start_line, end=end_line),
                        name=name
                    ))

        return functions

    def _extract_classes(self, node, source_code: str, file_path: str) -> list[Entity]:
        """Extract top-level class definitions."""
        classes = []

        for child in node.children:
            if child.type == "class_definition":
                name_node = child.child_by_field_name("name")
                if name_node:
                    name = source_code[name_node.start_byte:name_node.end_byte]
                    start_line = child.start_point[0]
                    end_line = child.end_point[0]

                    classes.append(Entity(
                        kind="class",
                        path=file_path,
                        extent=Location(start=start_line, end=end_line),
                        name=name
                    ))

        return classes

    def _extract_methods(self, node, source_code: str, file_path: str) -> list[Entity]:
        """Extract method definitions (functions inside classes)."""
        methods = []

        for child in node.children:
            if child.type == "class_definition":
                # Find the class body
                body = child.child_by_field_name("body")
                if body:
                    # Extract all function definitions inside the class body
                    for item in body.children:
                        if item.type == "function_definition":
                            name_node = item.child_by_field_name("name")
                            if name_node:
                                name = source_code[name_node.start_byte:name_node.end_byte]
                                start_line = item.start_point[0]
                                end_line = item.end_point[0]

                                methods.append(Entity(
                                    kind="method",
                                    path=file_path,
                                    extent=Location(start=start_line, end=end_line),
                                    name=name
                                ))

        return methods
