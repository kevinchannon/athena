"""Module for handling module-level docstrings with shebang and encoding support."""

import ast
import re


def detect_file_header(source_code: str) -> tuple[str | None, str | None, int]:
    """Detect shebang and encoding declaration at the start of a file.

    Args:
        source_code: Python source code to analyze

    Returns:
        Tuple of (shebang_line, encoding_line, header_end_line_idx)
        - shebang_line: The shebang line if present, None otherwise
        - encoding_line: The encoding declaration line if present, None otherwise
        - header_end_line_idx: 0-indexed line number where header ends (exclusive)
    """
    if not source_code:
        return None, None, 0

    lines = source_code.splitlines(keepends=True)
    shebang_line = None
    encoding_line = None
    current_line_idx = 0

    # Check for shebang (must be first line)
    if lines and lines[0].startswith("#!"):
        shebang_line = lines[0]
        current_line_idx = 1

    # Check for encoding declaration (PEP 263)
    # Can be on line 1 or 2 (if shebang is present)
    # Pattern: coding[:=]\s*([-\w.]+)
    encoding_pattern = re.compile(rb"coding[:=]\s*([-\w.]+)")

    if current_line_idx < len(lines):
        line_bytes = lines[current_line_idx].encode("utf-8")
        if encoding_pattern.search(line_bytes):
            encoding_line = lines[current_line_idx]
            current_line_idx += 1

    return shebang_line, encoding_line, current_line_idx


def extract_module_docstring(source_code: str) -> str | None:
    """Extract module-level docstring using AST detection.

    Args:
        source_code: Python source code

    Returns:
        Module docstring content (without quotes), or None if no docstring
    """
    if not source_code or not source_code.strip():
        return None

    try:
        tree = ast.parse(source_code)
        return ast.get_docstring(tree)
    except SyntaxError:
        # Invalid Python code
        return None


def update_module_docstring(source_code: str, new_docstring: str) -> str:
    """Update or insert module-level docstring, preserving file headers.

    Args:
        source_code: Original Python source code
        new_docstring: New docstring content (without triple quotes)

    Returns:
        Updated source code with new docstring and preserved headers
    """
    # Detect file headers
    shebang_line, encoding_line, header_end_idx = detect_file_header(source_code)

    lines = source_code.splitlines(keepends=True)

    # Extract the header (shebang + encoding)
    header_lines = lines[:header_end_idx]

    # Extract everything after the header
    body_lines = lines[header_end_idx:]

    # Find and remove existing module docstring
    # Parse the body to detect if there's a docstring
    body_source = "".join(body_lines)

    # Check if there's an existing docstring
    existing_docstring = None
    docstring_end_line_idx = None

    if body_source.strip():
        try:
            tree = ast.parse(body_source)
            existing_docstring = ast.get_docstring(tree)

            if existing_docstring is not None:
                # Find where the docstring ends in the body
                # The docstring is the first statement
                if tree.body and isinstance(tree.body[0], ast.Expr):
                    # Get the end line of the first expression (0-indexed within body)
                    docstring_node = tree.body[0]
                    # ast line numbers are 1-indexed
                    docstring_end_line_idx = docstring_node.end_lineno
        except SyntaxError:
            # If we can't parse, we'll just prepend the docstring
            pass

    # Build the new module docstring with proper formatting
    formatted_docstring = f'"""\n{new_docstring}\n"""\n'

    # Reconstruct the file
    result_lines = []

    # Add header
    result_lines.extend(header_lines)

    # Add new docstring
    result_lines.append(formatted_docstring)

    # Add the rest of the body (excluding old docstring if present)
    if docstring_end_line_idx is not None:
        # Skip lines that were part of the old docstring
        # docstring_end_line_idx is 1-indexed and represents the last line of the docstring
        result_lines.extend(body_lines[docstring_end_line_idx:])
    else:
        # No existing docstring, add all body lines
        result_lines.extend(body_lines)

    return "".join(result_lines)
