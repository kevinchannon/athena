import re

import tree_sitter_python
from tree_sitter import Language, Parser

from athena.models import (
    ClassInfo,
    Entity,
    FunctionInfo,
    Location,
    MethodInfo,
    ModuleInfo,
    Parameter,
    Signature,
)
from athena.parsers.base import BaseParser


class PythonParser(BaseParser):
    """Parser for extracting entities from Python source code using tree-sitter."""

    def __init__(self):
        self.language = Language(tree_sitter_python.language())
        self.parser = Parser(self.language)

    def _extract_text(self, source_code: str, start_byte: int, end_byte: int) -> str:
        """Extract text from source code using byte offsets.

        Tree-sitter returns byte offsets for UTF-8 encoded strings, but Python
        strings are Unicode. This helper converts properly.

        Args:
            source_code: The source code string
            start_byte: Start byte offset
            end_byte: End byte offset

        Returns:
            The extracted text as a string
        """
        source_bytes = source_code.encode("utf8")
        return source_bytes[start_byte:end_byte].decode("utf8")

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
        """Extract top-level function definitions, including decorated ones."""
        functions = []

        for child in node.children:
            func_node = None
            extent_node = None

            if child.type == "function_definition":
                func_node = child
                extent_node = child
            elif child.type == "decorated_definition":
                # Check if this decorated definition contains a function
                for subchild in child.children:
                    if subchild.type == "function_definition":
                        func_node = subchild
                        extent_node = child  # Use decorator's extent to include decorators
                        break

            if func_node:
                name_node = func_node.child_by_field_name("name")
                if name_node:
                    name = self._extract_text(source_code, name_node.start_byte, name_node.end_byte)
                    start_line = extent_node.start_point[0]
                    end_line = extent_node.end_point[0]

                    functions.append(Entity(
                        kind="function",
                        path=file_path,
                        extent=Location(start=start_line, end=end_line),
                        name=name
                    ))

        return functions

    def _extract_classes(self, node, source_code: str, file_path: str) -> list[Entity]:
        """Extract top-level class definitions, including decorated ones."""
        classes = []

        for child in node.children:
            class_node = None
            extent_node = None

            if child.type == "class_definition":
                class_node = child
                extent_node = child
            elif child.type == "decorated_definition":
                # Check if this decorated definition contains a class
                for subchild in child.children:
                    if subchild.type == "class_definition":
                        class_node = subchild
                        extent_node = child  # Use decorator's extent to include decorators
                        break

            if class_node:
                name_node = class_node.child_by_field_name("name")
                if name_node:
                    name = self._extract_text(source_code, name_node.start_byte, name_node.end_byte)
                    start_line = extent_node.start_point[0]
                    end_line = extent_node.end_point[0]

                    classes.append(Entity(
                        kind="class",
                        path=file_path,
                        extent=Location(start=start_line, end=end_line),
                        name=name
                    ))

        return classes

    def _extract_methods(self, node, source_code: str, file_path: str) -> list[Entity]:
        """Extract method definitions (functions inside classes), including decorated ones."""
        methods = []

        for child in node.children:
            class_node = None

            # Handle both regular and decorated classes
            if child.type == "class_definition":
                class_node = child
            elif child.type == "decorated_definition":
                # Check if this decorated definition contains a class
                for subchild in child.children:
                    if subchild.type == "class_definition":
                        class_node = subchild
                        break

            if class_node:
                # Get class name
                class_name_node = class_node.child_by_field_name("name")
                if not class_name_node:
                    continue
                class_name = self._extract_text(source_code, class_name_node.start_byte, class_name_node.end_byte)

                # Find the class body
                body = class_node.child_by_field_name("body")
                if body:
                    # Extract all function definitions inside the class body
                    for item in body.children:
                        method_node = None
                        extent_node = None

                        if item.type == "function_definition":
                            method_node = item
                            extent_node = item
                        elif item.type == "decorated_definition":
                            # Check if this decorated definition contains a method
                            for subitem in item.children:
                                if subitem.type == "function_definition":
                                    method_node = subitem
                                    extent_node = item  # Use decorator's extent
                                    break

                        if method_node:
                            name_node = method_node.child_by_field_name("name")
                            if name_node:
                                method_name = self._extract_text(source_code, name_node.start_byte, name_node.end_byte)
                                start_line = extent_node.start_point[0]
                                end_line = extent_node.end_point[0]

                                methods.append(Entity(
                                    kind="method",
                                    path=file_path,
                                    extent=Location(start=start_line, end=end_line),
                                    name=f"{class_name}.{method_name}"
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
                        return self._extract_text(source_code, string_child.start_byte, string_child.end_byte)
                # If no string_content found, the string might be empty
                # Try extracting the whole string and remove quotes
                text = self._extract_text(source_code, child.start_byte, child.end_byte)
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
                param_name = self._extract_text(source_code, child.start_byte, child.end_byte)

            elif child.type == "typed_parameter":
                # Parameter with type hint: def foo(x: int):
                # Structure: typed_parameter -> identifier, :, type
                for subchild in child.children:
                    if subchild.type == "identifier" and param_name is None:
                        param_name = self._extract_text(source_code, subchild.start_byte, subchild.end_byte)
                    elif subchild.type == "type":
                        param_type = self._extract_text(source_code, subchild.start_byte, subchild.end_byte)

            elif child.type == "default_parameter":
                # Parameter with default value: def foo(x=5):
                name_node = child.child_by_field_name("name")
                value_node = child.child_by_field_name("value")
                if name_node:
                    param_name = self._extract_text(source_code, name_node.start_byte, name_node.end_byte)
                if value_node:
                    param_default = self._extract_text(source_code, value_node.start_byte, value_node.end_byte)

            elif child.type == "typed_default_parameter":
                # Parameter with type and default: def foo(x: int = 5):
                name_node = child.child_by_field_name("name")
                type_node = child.child_by_field_name("type")
                value_node = child.child_by_field_name("value")
                if name_node:
                    param_name = self._extract_text(source_code, name_node.start_byte, name_node.end_byte)
                if type_node:
                    param_type = self._extract_text(source_code, type_node.start_byte, type_node.end_byte)
                if value_node:
                    param_default = self._extract_text(source_code, value_node.start_byte, value_node.end_byte)

            elif child.type in ("list_splat_pattern", "dictionary_splat_pattern"):
                # Handle *args and **kwargs
                # list_splat_pattern is *args, dictionary_splat_pattern is **kwargs
                text = self._extract_text(source_code, child.start_byte, child.end_byte)
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
            return self._extract_text(source_code, return_type_node.start_byte, return_type_node.end_byte)
        return None

    def _format_signature(self, name: str, params: list[Parameter], return_type: str | None) -> str:
        """Format a signature as a string.

        Args:
            name: Function/method name
            params: List of Parameter objects
            return_type: Return type annotation or None

        Returns:
            Formatted signature string like "func(x: int = 5, y: str) -> bool"
        """
        # Format each parameter
        param_strs = []
        for param in params:
            if param.type and param.default:
                # Has both type and default: x: int = 5
                param_strs.append(f"{param.name}: {param.type} = {param.default}")
            elif param.type:
                # Has type only: x: int
                param_strs.append(f"{param.name}: {param.type}")
            elif param.default:
                # Has default only: x = 5
                param_strs.append(f"{param.name} = {param.default}")
            else:
                # Plain parameter: x
                param_strs.append(param.name)

        # Build signature
        sig = f"{name}({', '.join(param_strs)})"

        # Add return type if present
        if return_type:
            sig += f" -> {return_type}"

        return sig

    def extract_entity_info(
        self,
        source_code: str,
        file_path: str,
        entity_name: str | None = None
    ) -> FunctionInfo | ClassInfo | MethodInfo | ModuleInfo | None:
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
            return ModuleInfo(
                path=file_path,
                extent=extent,
                summary=docstring
            )

        # Search for the named entity
        # Check functions and classes (including decorated ones)
        for child in root_node.children:
            func_node = None
            class_node = None
            extent_node = None

            # Handle direct function definitions
            if child.type == "function_definition":
                func_node = child
                extent_node = child
            # Handle decorated definitions
            elif child.type == "decorated_definition":
                for subchild in child.children:
                    if subchild.type == "function_definition":
                        func_node = subchild
                        extent_node = child  # Use decorator's extent
                    elif subchild.type == "class_definition":
                        class_node = subchild
                        extent_node = child  # Use decorator's extent
            # Handle direct class definitions
            elif child.type == "class_definition":
                class_node = child
                extent_node = child

            # Check if we found a matching function
            if func_node:
                name_node = func_node.child_by_field_name("name")
                if name_node:
                    name = self._extract_text(source_code, name_node.start_byte, name_node.end_byte)
                    if name == entity_name:
                        return self._build_entity_info_for_function(func_node, source_code, file_path, extent_node=extent_node)

            # Check if we found a matching class or methods inside it
            if class_node:
                name_node = class_node.child_by_field_name("name")
                if name_node:
                    class_name = self._extract_text(source_code, name_node.start_byte, name_node.end_byte)
                    if class_name == entity_name:
                        return self._build_entity_info_for_class(class_node, source_code, file_path, extent_node=extent_node)

                    # Also check methods inside this class
                    body = class_node.child_by_field_name("body")
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
                                        method_extent_node = item  # Use decorator's extent
                                        break

                            if method_node:
                                method_name_node = method_node.child_by_field_name("name")
                                if method_name_node:
                                    method_name = self._extract_text(source_code, method_name_node.start_byte, method_name_node.end_byte)
                                    if method_name == entity_name:
                                        # Pass class_name to indicate this is a method
                                        return self._build_entity_info_for_function(
                                            method_node, source_code, file_path, class_name=class_name, extent_node=method_extent_node
                                        )

        return None

    def _build_entity_info_for_function(
        self, node, source_code: str, file_path: str, class_name: str | None = None, extent_node=None
    ) -> FunctionInfo | MethodInfo:
        """Build FunctionInfo or MethodInfo for a function or method.

        Args:
            node: function_definition tree-sitter node
            source_code: Source code string
            file_path: Relative file path
            class_name: Class name if this is a method, None for top-level functions
            extent_node: Optional node to use for extent (e.g., decorated_definition to include decorators)

        Returns:
            FunctionInfo if class_name is None, MethodInfo otherwise
        """
        name_node = node.child_by_field_name("name")
        name = self._extract_text(source_code, name_node.start_byte, name_node.end_byte) if name_node else ""

        # Extract signature components
        params = self._extract_parameters(node, source_code)
        return_type = self._extract_return_type(node, source_code)
        sig = Signature(name=name, args=params, return_type=return_type)

        # Extract docstring
        docstring = self._extract_docstring(node, source_code)

        # Extract extent (use extent_node if provided to include decorators)
        extent_source = extent_node if extent_node is not None else node
        start_line = extent_source.start_point[0]
        end_line = extent_source.end_point[0]
        extent = Location(start=start_line, end=end_line)

        # Return MethodInfo if it's a method, otherwise FunctionInfo
        if class_name:
            return MethodInfo(
                name=f"{class_name}.{name}",
                path=file_path,
                extent=extent,
                sig=sig,
                summary=docstring
            )
        else:
            return FunctionInfo(
                path=file_path,
                extent=extent,
                sig=sig,
                summary=docstring
            )

    def _build_entity_info_for_class(self, node, source_code: str, file_path: str, extent_node=None) -> ClassInfo:
        """Build ClassInfo for a class, including formatted method signatures.

        Args:
            node: class_definition tree-sitter node
            source_code: Source code string
            file_path: Relative file path
            extent_node: Optional node to use for extent (e.g., decorated_definition to include decorators)
        """
        # Get class name
        name_node = node.child_by_field_name("name")
        class_name = self._extract_text(source_code, name_node.start_byte, name_node.end_byte) if name_node else ""

        # Extract docstring
        docstring = self._extract_docstring(node, source_code)

        # Extract extent (use extent_node if provided to include decorators)
        extent_source = extent_node if extent_node is not None else node
        start_line = extent_source.start_point[0]
        end_line = extent_source.end_point[0]
        extent = Location(start=start_line, end=end_line)

        # Extract methods
        methods = []
        body = node.child_by_field_name("body")
        if body:
            for item in body.children:
                if item.type == "function_definition":
                    method_name_node = item.child_by_field_name("name")
                    if method_name_node:
                        method_name = self._extract_text(source_code, method_name_node.start_byte, method_name_node.end_byte)
                        params = self._extract_parameters(item, source_code)
                        return_type = self._extract_return_type(item, source_code)
                        # Format as string signature
                        formatted_sig = self._format_signature(method_name, params, return_type)
                        methods.append(formatted_sig)

        return ClassInfo(
            path=file_path,
            extent=extent,
            methods=methods,
            summary=docstring
        )

    @staticmethod
    def parse_athena_tag(docstring: str) -> str | None:
        """Extract hash from @athena tag in docstring.

        Args:
            docstring: Docstring content to parse

        Returns:
            12-character hex hash if tag found and valid, None otherwise
        """
        if not docstring:
            return None

        # Look for @athena: <hash> pattern
        pattern = r"@athena:\s*([0-9a-f]{12})"
        match = re.search(pattern, docstring, re.IGNORECASE)

        if match:
            return match.group(1)

        return None

    @staticmethod
    def update_athena_tag(docstring: str, new_hash: str) -> str:
        """Update or insert @athena tag in docstring.

        If docstring is empty or None, creates a minimal docstring with the tag.
        If tag exists, updates it. If tag doesn't exist, appends it.

        Args:
            docstring: Existing docstring content (may be None or empty)
            new_hash: New 12-character hex hash to insert

        Returns:
            Updated docstring with @athena tag
        """
        # Handle empty/None docstring - create minimal docstring
        if not docstring or not docstring.strip():
            return f"@athena: {new_hash}"

        # Check if tag already exists (match any 12 non-whitespace chars, not just hex)
        pattern = r"@athena:\s*\S{12}"
        if re.search(pattern, docstring, re.IGNORECASE):
            # Update existing tag
            return re.sub(
                pattern, f"@athena: {new_hash}", docstring, flags=re.IGNORECASE
            )
        else:
            # Append tag to end of docstring
            # Ensure there's a newline before the tag if docstring doesn't end with one
            if docstring.endswith("\n"):
                return f"{docstring}@athena: {new_hash}"
            else:
                return f"{docstring}\n@athena: {new_hash}"

    @staticmethod
    def validate_athena_tag(tag: str) -> bool:
        """Validate that a tag is a proper 12-character hex hash.

        Args:
            tag: Tag string to validate (without @athena: prefix)

        Returns:
            True if valid 12-character hex hash, False otherwise
        """
        if not tag:
            return False

        # Must be exactly 12 characters and all hex
        pattern = r"^[0-9a-f]{12}$"
        return bool(re.match(pattern, tag, re.IGNORECASE))
