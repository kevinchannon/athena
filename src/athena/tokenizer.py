"""Code-aware tokenization for BM25 search.

This module provides tokenization functions that handle code identifiers
(snake_case, camelCase) in addition to natural language text.
"""

import re


def _split_camel_case(text: str) -> list[str]:
    """Split camelCase and PascalCase text into separate words.

    Args:
        text: A string that may contain camelCase or PascalCase.

    Returns:
        List of words extracted from camelCase/PascalCase text.

    Examples:
        >>> _split_camel_case("handleJwtAuth")
        ['handle', 'Jwt', 'Auth']
        >>> _split_camel_case("HTTPSConnection")
        ['HTTPS', 'Connection']
    """
    # Split on transitions from lowercase to uppercase
    # Pattern: lowercase followed by uppercase -> insert boundary
    result = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    # Split on transitions from multiple uppercase to lowercase (for acronyms)
    # Pattern: uppercase followed by uppercase then lowercase -> insert boundary before last uppercase
    result = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', result)
    return result.split()


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

    # Step 1: Split on underscores, hyphens, whitespace, and common punctuation
    # Keep alphanumeric sequences together for now
    tokens = re.findall(r'\w+', text)

    # Step 2: Split each token on camelCase
    result = []
    for token in tokens:
        # Split camelCase if present
        if re.search(r'[a-z][A-Z]', token):
            # Has camelCase pattern
            parts = _split_camel_case(token)
            result.extend(parts)
        else:
            result.append(token)

    # Step 3: Lowercase all tokens
    result = [t.lower() for t in result]

    # Step 4: Filter empty tokens
    return [t for t in result if t]
