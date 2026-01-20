"""Tests for tokenizer module."""

import pytest

from athena.tokenizer import tokenize


class TestTokenizeSnakeCase:
    """Tests for snake_case tokenization."""

    def test_tokenize_snake_case(self):
        """Test tokenizing standard snake_case identifier."""
        assert tokenize("handle_jwt_auth") == ["handle", "jwt", "auth"]

    def test_tokenize_single_word(self):
        """Test tokenizing single word without separators."""
        assert tokenize("authentication") == ["authentication"]

    def test_tokenize_snake_case_with_numbers(self):
        """Test tokenizing snake_case with numbers."""
        assert tokenize("handle_v2_auth") == ["handle", "v2", "auth"]

    def test_tokenize_leading_underscore(self):
        """Test tokenizing identifier with leading underscore."""
        assert tokenize("_private_method") == ["private", "method"]

    def test_tokenize_trailing_underscore(self):
        """Test tokenizing identifier with trailing underscore."""
        assert tokenize("method_name_") == ["method", "name"]

    def test_tokenize_double_underscore(self):
        """Test tokenizing identifier with double underscores."""
        assert tokenize("__init__") == ["init"]

    def test_tokenize_consecutive_underscores(self):
        """Test tokenizing malformed identifier with consecutive underscores."""
        assert tokenize("handle__auth") == ["handle", "auth"]


class TestTokenizeCamelCase:
    """Tests for camelCase tokenization."""

    def test_tokenize_camel_case(self):
        """Test tokenizing standard camelCase identifier."""
        assert tokenize("handleJwtAuth") == ["handle", "jwt", "auth"]

    def test_tokenize_pascal_case(self):
        """Test tokenizing PascalCase identifier."""
        assert tokenize("HandleJwtAuth") == ["handle", "jwt", "auth"]

    def test_tokenize_camel_case_with_acronym(self):
        """Test tokenizing camelCase with acronym at start."""
        assert tokenize("jwtAuthHandler") == ["jwt", "auth", "handler"]

    def test_tokenize_camel_case_with_multiple_acronyms(self):
        """Test tokenizing camelCase with multiple acronyms."""
        assert tokenize("HTTPSConnectionAPI") == ["https", "connection", "api"]


class TestTokenizeMixedCase:
    """Tests for mixed snake_case and camelCase."""

    def test_tokenize_mixed_case(self):
        """Test tokenizing mixed snake_case and camelCase."""
        assert tokenize("JWT_authHandler") == ["jwt", "auth", "handler"]

    def test_tokenize_snake_case_with_camel_parts(self):
        """Test tokenizing snake_case with camelCase parts."""
        assert tokenize("handle_JwtAuth_method") == ["handle", "jwt", "auth", "method"]


class TestTokenizeDocstringText:
    """Tests for natural language text tokenization."""

    def test_tokenize_simple_sentence(self):
        """Test tokenizing simple sentence with spaces."""
        assert tokenize("JWT API authentication") == ["jwt", "api", "authentication"]

    def test_tokenize_sentence_with_punctuation(self):
        """Test tokenizing sentence with common punctuation."""
        assert tokenize("Handle JWT authentication, parse tokens.") == [
            "handle", "jwt", "authentication", "parse", "tokens"
        ]

    def test_tokenize_sentence_with_hyphens(self):
        """Test tokenizing sentence with hyphenated words."""
        assert tokenize("user-defined session-based authentication") == [
            "user", "defined", "session", "based", "authentication"
        ]

    def test_tokenize_sentence_with_parentheses(self):
        """Test tokenizing sentence with parentheses."""
        assert tokenize("authentication (JWT tokens)") == ["authentication", "jwt", "tokens"]

    def test_tokenize_sentence_with_quotes(self):
        """Test tokenizing sentence with quotes."""
        assert tokenize('Handle "JWT" authentication') == ["handle", "jwt", "authentication"]


class TestTokenizeAcronyms:
    """Tests for acronym preservation."""

    def test_tokenize_preserves_acronyms(self):
        """Test that uppercase acronyms are lowercased."""
        assert tokenize("JWT API") == ["jwt", "api"]

    def test_tokenize_all_caps_with_underscores(self):
        """Test tokenizing all-caps constant with underscores."""
        assert tokenize("MAX_JWT_SIZE") == ["max", "jwt", "size"]

    def test_tokenize_single_letter_acronym(self):
        """Test tokenizing single-letter words."""
        assert tokenize("a simple test") == ["a", "simple", "test"]


class TestTokenizeEmptyAndEdgeCases:
    """Tests for empty strings and edge cases."""

    def test_tokenize_empty_string(self):
        """Test tokenizing empty string."""
        assert tokenize("") == []

    def test_tokenize_whitespace_only(self):
        """Test tokenizing whitespace-only string."""
        assert tokenize("   ") == []

    def test_tokenize_punctuation_only(self):
        """Test tokenizing string with only punctuation."""
        assert tokenize(".,;:!?") == []

    def test_tokenize_underscores_only(self):
        """Test tokenizing string with only underscores."""
        assert tokenize("___") == []

    def test_tokenize_numbers_only(self):
        """Test tokenizing string with only numbers."""
        assert tokenize("12345") == ["12345"]

    def test_tokenize_mixed_numbers_and_letters(self):
        """Test tokenizing mixed alphanumeric string."""
        assert tokenize("v2api") == ["v2api"]


class TestTokenizeSpecialCharacters:
    """Tests for special character handling."""

    def test_tokenize_with_brackets(self):
        """Test tokenizing text with brackets."""
        assert tokenize("method[index]") == ["method", "index"]

    def test_tokenize_with_dots(self):
        """Test tokenizing text with dots (module paths)."""
        assert tokenize("module.submodule.function") == ["module", "submodule", "function"]

    def test_tokenize_with_slashes(self):
        """Test tokenizing text with slashes."""
        assert tokenize("path/to/file") == ["path", "to", "file"]

    def test_tokenize_with_equals(self):
        """Test tokenizing text with equals sign."""
        assert tokenize("key=value") == ["key", "value"]

    def test_tokenize_with_at_symbol(self):
        """Test tokenizing text with @ symbol."""
        assert tokenize("@decorator") == ["decorator"]


class TestTokenizeComplexCases:
    """Tests for complex real-world cases."""

    def test_tokenize_function_call(self):
        """Test tokenizing function call syntax."""
        assert tokenize("handleJwtAuth(token)") == ["handle", "jwt", "auth", "token"]

    def test_tokenize_docstring_line(self):
        """Test tokenizing realistic docstring line."""
        result = tokenize("Parse JWT tokens and validate authentication credentials")
        assert result == ["parse", "jwt", "tokens", "and", "validate", "authentication", "credentials"]

    def test_tokenize_code_with_operators(self):
        """Test tokenizing code snippet with operators."""
        assert tokenize("x + y == z") == ["x", "y", "z"]

    def test_tokenize_url_like_string(self):
        """Test tokenizing URL-like string."""
        result = tokenize("https://api.example.com/v2/auth")
        assert "https" in result
        assert "api" in result
        assert "example" in result
        assert "com" in result
        assert "v2" in result
        assert "auth" in result

    def test_tokenize_type_annotation(self):
        """Test tokenizing type annotation syntax."""
        assert tokenize("list[str]") == ["list", "str"]


class TestTokenizeUnicode:
    """Tests for Unicode character handling."""

    def test_tokenize_unicode_text(self):
        """Test tokenizing text with Unicode characters."""
        # Non-ASCII characters should be filtered out by \w+ pattern
        assert tokenize("café résumé") == ["caf", "r", "sum"]

    def test_tokenize_emoji(self):
        """Test tokenizing text with emoji."""
        # Emoji should be filtered out
        assert tokenize("handle 🔒 authentication") == ["handle", "authentication"]


class TestTokenizeCaseSensitivity:
    """Tests for case-insensitive behavior."""

    def test_tokenize_is_case_insensitive(self):
        """Test that tokenization produces lowercase output."""
        assert tokenize("HANDLE_JWT_AUTH") == ["handle", "jwt", "auth"]
        assert tokenize("HandleJwtAuth") == ["handle", "jwt", "auth"]
        assert tokenize("Handle JWT Auth") == ["handle", "jwt", "auth"]

    def test_tokenize_mixed_case_produces_same_result(self):
        """Test that different cases produce identical tokens."""
        snake = tokenize("handle_jwt_auth")
        camel = tokenize("handleJwtAuth")
        upper = tokenize("HANDLE_JWT_AUTH")
        assert snake == camel == upper
