"""Code-aware tokenization for BM25 search.

This module provides tokenization functions that handle code identifiers
(snake_case, camelCase) in addition to natural language text.
"""

import re


def _split_on_case_transitions(text: str) -> str:
    """Insert spaces at camelCase boundaries for proper word splitting.

    Handles both simple camelCase (aB -> a B) and acronyms (HTTPSConn -> HTTPS Conn).
    """
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    text = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', text)
    return text


def _extract_alphanumeric_tokens(text: str) -> list[str]:
    """Extract ASCII alphanumeric sequences, excluding non-ASCII characters."""
    return re.findall(r'[a-zA-Z0-9]+', text)


def _has_camel_case(text: str) -> bool:
    """Check if text contains camelCase pattern (lowercase followed by uppercase)."""
    return bool(re.search(r'[a-z][A-Z]', text))


def tokenize(text: str) -> list[str]:
    """Tokenize text with code-aware splitting.

    Handles both natural language text and code identifiers:
    - Splits on underscores and hyphens
    - Splits camelCase: handleJwtAuth -> ['handle', 'jwt', 'auth']
    - Splits snake_case: handle_jwt_auth -> ['handle', 'jwt', 'auth']
    - Preserves acronyms: JWT -> ['jwt']
    - Splits on whitespace and punctuation
    - Lowercases all tokens
    - Filters empty tokens

    Args:
        text: Input text to tokenize (docstring, query, or code identifier).

    Returns:
        List of lowercase tokens with empty strings filtered out.

    Examples:
        >>> tokenize("handle_jwt_auth")
        ['handle', 'jwt', 'auth']
        >>> tokenize("handleJwtAuth")
        ['handle', 'jwt', 'auth']
        >>> tokenize("JWT API authentication")
        ['jwt', 'api', 'authentication']
        >>> tokenize("")
        []
    """
    if not text:
        return []

    text_with_spaces = _split_on_case_transitions(text)
    tokens = _extract_alphanumeric_tokens(text_with_spaces)
    lowercased = [t.lower() for t in tokens]
    return [t for t in lowercased if t]
