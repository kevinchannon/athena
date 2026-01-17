"""Module for updating docstrings in source code files."""

from athena.models import Location


def update_docstring_in_source(
    source_code: str, entity_location: Location, new_docstring: str
) -> str:
    """Replace or insert docstring in source code for a given entity.

    This function updates the docstring at the specified location in the source code.
    It handles:
    - Entities with existing docstrings (updates them)
    - Entities without docstrings (inserts new docstring)
    - Preservation of indentation and formatting

    Args:
        source_code: Full source code string
        entity_location: Location of the entity (start/end line numbers, 0-indexed)
        new_docstring: New docstring content (without triple quotes)

    Returns:
        Updated source code with new docstring

    Raises:
        ValueError: If entity_location is invalid
    """
    lines = source_code.splitlines(keepends=True)

    # Validate location
    if entity_location.start < 0 or entity_location.end >= len(lines):
        raise ValueError(f"Invalid entity location: {entity_location}")

    # Find the definition line (function/class declaration)
    # The entity location may include decorators, so we need to find the actual def/class line
    def_line_idx = entity_location.start

    # Search for the actual def/class line (skip any decorators)
    for i in range(entity_location.start, min(entity_location.end + 1, len(lines))):
        stripped = lines[i].lstrip()
        if stripped.startswith('def ') or stripped.startswith('class '):
            def_line_idx = i
            break

    # Determine indentation of the entity
    def_line = lines[def_line_idx]
    indent = len(def_line) - len(def_line.lstrip())
    entity_indent = " " * indent

    # Determine the body start (line after def/class declaration)
    # For multi-line signatures, we need to find the line with the closing colon
    # Search forward from def_line_idx to find a line ending with ':'
    body_start_idx = def_line_idx + 1
    for i in range(def_line_idx, min(entity_location.end + 1, len(lines))):
        line = lines[i]
        # Check if line ends with ':' (ignoring trailing whitespace and comments)
        stripped = line.rstrip()
        if stripped.endswith(':'):
            body_start_idx = i + 1
            break

    # Check if there's already a docstring
    # A docstring is the first non-empty statement in the body
    docstring_start_idx = None
    docstring_end_idx = None

    # Skip empty lines after definition
    search_idx = body_start_idx
    while search_idx <= entity_location.end and search_idx < len(lines):
        line = lines[search_idx]
        stripped = line.strip()

        if not stripped:
            # Empty line, continue
            search_idx += 1
            continue

        # Check if this line starts a docstring (triple quotes)
        if stripped.startswith('"""') or stripped.startswith("'''"):
            # Found docstring start
            docstring_start_idx = search_idx
            quote_type = '"""' if stripped.startswith('"""') else "'''"

            # Check if it's a single-line docstring
            # Remove leading quote
            after_start_quote = stripped[3:]
            if after_start_quote.endswith(quote_type):
                # Single-line docstring
                docstring_end_idx = search_idx
            else:
                # Multi-line docstring - find the end
                search_idx += 1
                while search_idx <= entity_location.end and search_idx < len(lines):
                    if quote_type in lines[search_idx]:
                        docstring_end_idx = search_idx
                        break
                    search_idx += 1

            break
        else:
            # Non-docstring statement found, no docstring exists
            break

    # Format the new docstring with proper indentation
    docstring_indent = entity_indent + "    "  # One level deeper than entity
    formatted_lines = []
    formatted_lines.append(f'{docstring_indent}"""\n')

    # Add docstring content with proper indentation
    # Strip existing indentation from each line and apply consistent indentation
    for line in new_docstring.splitlines():
        stripped = line.lstrip()
        if stripped:  # Non-empty line
            formatted_lines.append(f"{docstring_indent}{stripped}\n")
        else:  # Empty line
            formatted_lines.append("\n")

    formatted_lines.append(f'{docstring_indent}"""\n')

    # Now insert or replace the docstring
    if docstring_start_idx is not None and docstring_end_idx is not None:
        # Replace existing docstring
        # Remove old docstring lines
        result_lines = (
            lines[:docstring_start_idx]
            + formatted_lines
            + lines[docstring_end_idx + 1 :]
        )
    else:
        # Insert new docstring after definition line
        result_lines = lines[:body_start_idx] + formatted_lines + lines[body_start_idx:]

    return "".join(result_lines)
