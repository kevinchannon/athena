"""Module for handling module-level docstrings with shebang and encoding support."""

import ast
import re


def detect_file_header(source_code: str) -> tuple[str | None, str | None, int]:
    r"""Detect shebang and encoding declaration at the start of a file.

    Per PEP 263, encoding can be on line 1 or 2 (if shebang is present).
    Uses pattern: coding[:=]\s*([-\w.]+)

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

    if lines and lines[0].startswith("#!"):
        shebang_line = lines[0]
        current_line_idx = 1

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


def _split_header_and_body(
    lines: list[str], header_end_idx: int
) -> tuple[list[str], list[str]]:
    """Split source lines into header and body sections."""
    header_lines = lines[:header_end_idx]
    body_lines = lines[header_end_idx:]
    return header_lines, body_lines


def _find_existing_docstring_end(body_lines: list[str]) -> int | None:
    """Find the end line index of existing module docstring in body.

    Returns:
        Line index where docstring ends (1-indexed), or None if no docstring
    """
    body_source = "".join(body_lines)
    if not body_source.strip():
        return None

    try:
        tree = ast.parse(body_source)
        if ast.get_docstring(tree) is not None:
            if tree.body and isinstance(tree.body[0], ast.Expr):
                return tree.body[0].end_lineno
    except SyntaxError:
        pass

    return None


def _format_docstring(docstring: str) -> str:
    """Format docstring with triple quotes and newlines."""
    return f'"""\n{docstring}\n"""\n'


def _reconstruct_file(
    header_lines: list[str],
    formatted_docstring: str,
    body_lines: list[str],
    docstring_end_idx: int | None,
) -> str:
    """Reconstruct file from header, new docstring, and body without old docstring."""
    result_lines = []
    result_lines.extend(header_lines)
    result_lines.append(formatted_docstring)

    if docstring_end_idx is not None:
        result_lines.extend(body_lines[docstring_end_idx:])
    else:
        result_lines.extend(body_lines)

    return "".join(result_lines)


def update_module_docstring(source_code: str, new_docstring: str) -> str:
    """Update or insert module-level docstring, preserving file headers.

    Args:
        source_code: Original Python source code
        new_docstring: New docstring content (without triple quotes)

    Returns:
        Updated source code with new docstring and preserved headers
    """
    shebang_line, encoding_line, header_end_idx = detect_file_header(source_code)
    lines = source_code.splitlines(keepends=True)

    header_lines, body_lines = _split_header_and_body(lines, header_end_idx)
    docstring_end_idx = _find_existing_docstring_end(body_lines)
    formatted_docstring = _format_docstring(new_docstring)

    return _reconstruct_file(header_lines, formatted_docstring, body_lines, docstring_end_idx)
