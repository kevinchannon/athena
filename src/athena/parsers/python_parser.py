import tree_sitter_python
from tree_sitter import Language, Parser

from athena.models import Entity, EntityInfo, Location, Parameter, Signature
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

    def _extract_docstring(self, node, source_code: str) -> str | None:
        """Extract docstring from function/class/module node.

        For functions/classes: Check if first child of body block is expression_statement
        containing a string node.

        For modules: Check if first child of root is expression_statement with string.

        Args:
            node: Tree-sitter node (function_definition, class_definition, or module root)
            source_code: Source code string for text extraction

        Returns:
            Docstring content without quotes, or None if no docstring.
        """
        # For function/class definitions, get the body block first
        if node.type in ("function_definition", "class_definition"):
            body = node.child_by_field_name("body")
            if not body or len(body.children) == 0:
                return None
            first_child = body.children[0]
        else:
            # For module nodes, check first child directly
            if len(node.children) == 0:
                return None
            first_child = node.children[0]

        # Check if first child is an expression_statement
        if first_child.type != "expression_statement":
            return None

        # Check if the expression_statement contains a string
        for child in first_child.children:
            if child.type == "string":
                # Extract the string content (without quotes)
                # String node structure: string_start, string_content, string_end
                for string_child in child.children:
                    if string_child.type == "string_content":
                        return source_code[string_child.start_byte:string_child.end_byte]
                # If no string_content found, the string might be empty
                # Try extracting the whole string and remove quotes
                text = source_code[child.start_byte:child.end_byte]
                # Handle triple quotes and single quotes
                if text.startswith('"""') or text.startswith("'''"):
                    return text[3:-3]
                elif text.startswith('"') or text.startswith("'"):
                    return text[1:-1]

        return None

    def _extract_parameters(self, node, source_code: str) -> list[Parameter]:
        """Extract parameter list from function/method definition.

        Args:
            node: function_definition tree-sitter node
            source_code: Source code string for text extraction

        Returns:
            List of Parameter objects
        """
        parameters = []

        # Get the parameters node
        params_node = node.child_by_field_name("parameters")
        if not params_node:
            return parameters

        # Iterate through parameter nodes
        for child in params_node.children:
            # Skip punctuation tokens (, ), ,
            if child.type in ("(", ")", ","):
                continue

            param_name = None
            param_type = None
            param_default = None

            if child.type == "identifier":
                # Simple parameter: def foo(x):
                param_name = source_code[child.start_byte:child.end_byte]

            elif child.type == "typed_parameter":
                # Parameter with type hint: def foo(x: int):
                # Structure: typed_parameter -> identifier, :, type
                for subchild in child.children:
                    if subchild.type == "identifier" and param_name is None:
                        param_name = source_code[subchild.start_byte:subchild.end_byte]
                    elif subchild.type == "type":
                        param_type = source_code[subchild.start_byte:subchild.end_byte]

            elif child.type == "default_parameter":
                # Parameter with default value: def foo(x=5):
                name_node = child.child_by_field_name("name")
                value_node = child.child_by_field_name("value")
                if name_node:
                    param_name = source_code[name_node.start_byte:name_node.end_byte]
                if value_node:
                    param_default = source_code[value_node.start_byte:value_node.end_byte]

            elif child.type == "typed_default_parameter":
                # Parameter with type and default: def foo(x: int = 5):
                name_node = child.child_by_field_name("name")
                type_node = child.child_by_field_name("type")
                value_node = child.child_by_field_name("value")
                if name_node:
                    param_name = source_code[name_node.start_byte:name_node.end_byte]
                if type_node:
                    param_type = source_code[type_node.start_byte:type_node.end_byte]
                if value_node:
                    param_default = source_code[value_node.start_byte:value_node.end_byte]

            elif child.type in ("list_splat_pattern", "dictionary_splat_pattern"):
                # Handle *args and **kwargs
                # list_splat_pattern is *args, dictionary_splat_pattern is **kwargs
                text = source_code[child.start_byte:child.end_byte]
                param_name = text  # Keep the * or ** prefix

            # Add parameter if we found a name
            if param_name:
                parameters.append(Parameter(
                    name=param_name,
                    type=param_type,
                    default=param_default
                ))

        return parameters

    def _extract_return_type(self, node, source_code: str) -> str | None:
        """Extract return type annotation from function/method definition.

        Args:
            node: function_definition tree-sitter node
            source_code: Source code string for text extraction

        Returns:
            Return type as string, or None if no annotation.
        """
        return_type_node = node.child_by_field_name("return_type")
        if return_type_node:
            return source_code[return_type_node.start_byte:return_type_node.end_byte]
        return None

    def extract_entity_info(
        self,
        source_code: str,
        file_path: str,
        entity_name: str | None = None
    ) -> EntityInfo | None:
        """Extract detailed information about a specific entity.

        Args:
            source_code: Python source code
            file_path: File path (for EntityInfo.path)
            entity_name: Entity name to find, or None for module-level info

        Returns:
            EntityInfo object, or None if entity not found
        """
        tree = self.parser.parse(bytes(source_code, "utf8"))
        root_node = tree.root_node

        # If no entity name, return module-level info
        if entity_name is None:
            docstring = self._extract_docstring(root_node, source_code)
            # Module extent is from start to end of file
            lines = source_code.splitlines()
            extent = Location(start=0, end=len(lines) - 1 if lines else 0)
            return EntityInfo(
                path=file_path,
                extent=extent,
                sig=None,  # Modules don't have signatures
                summary=docstring
            )

        # Search for the named entity
        # Check functions
        for child in root_node.children:
            if child.type == "function_definition":
                name_node = child.child_by_field_name("name")
                if name_node:
                    name = source_code[name_node.start_byte:name_node.end_byte]
                    if name == entity_name:
                        return self._build_entity_info_for_function(child, source_code, file_path)

            # Check classes
            elif child.type == "class_definition":
                name_node = child.child_by_field_name("name")
                if name_node:
                    name = source_code[name_node.start_byte:name_node.end_byte]
                    if name == entity_name:
                        return self._build_entity_info_for_class(child, source_code, file_path)

                # Also check methods inside this class
                body = child.child_by_field_name("body")
                if body:
                    for item in body.children:
                        if item.type == "function_definition":
                            method_name_node = item.child_by_field_name("name")
                            if method_name_node:
                                method_name = source_code[method_name_node.start_byte:method_name_node.end_byte]
                                if method_name == entity_name:
                                    return self._build_entity_info_for_function(item, source_code, file_path)

        return None

    def _build_entity_info_for_function(self, node, source_code: str, file_path: str) -> EntityInfo:
        """Build EntityInfo for a function or method."""
        name_node = node.child_by_field_name("name")
        name = source_code[name_node.start_byte:name_node.end_byte] if name_node else ""

        # Extract signature components
        params = self._extract_parameters(node, source_code)
        return_type = self._extract_return_type(node, source_code)
        sig = Signature(name=name, args=params, return_type=return_type)

        # Extract docstring
        docstring = self._extract_docstring(node, source_code)

        # Extract extent
        start_line = node.start_point[0]
        end_line = node.end_point[0]
        extent = Location(start=start_line, end=end_line)

        return EntityInfo(
            path=file_path,
            extent=extent,
            sig=sig,
            summary=docstring
        )

    def _build_entity_info_for_class(self, node, source_code: str, file_path: str) -> EntityInfo:
        """Build EntityInfo for a class."""
        # Extract docstring
        docstring = self._extract_docstring(node, source_code)

        # Extract extent
        start_line = node.start_point[0]
        end_line = node.end_point[0]
        extent = Location(start=start_line, end=end_line)

        return EntityInfo(
            path=file_path,
            extent=extent,
            sig=None,  # Classes don't have callable signatures
            summary=docstring
        )
