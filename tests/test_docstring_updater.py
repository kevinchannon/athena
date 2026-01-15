"""Tests for docstring manipulation functionality."""

import pytest

from athena.docstring_updater import update_docstring_in_source
from athena.models import Location
from athena.parsers.python_parser import PythonParser


class TestParseAthenaTag:
    """Tests for PythonParser.parse_athena_tag."""

    def test_parse_tag_from_docstring(self):
        """Test extracting hash from valid @athena tag."""
        docstring = """Summary of function.

        @athena: a1b2c3d4e5f6
        """
        result = PythonParser.parse_athena_tag(docstring)
        assert result == "a1b2c3d4e5f6"

    def test_parse_tag_with_extra_whitespace(self):
        """Test parsing tag with varying whitespace."""
        docstring = "@athena:     abc123def456"
        result = PythonParser.parse_athena_tag(docstring)
        assert result == "abc123def456"

    def test_parse_tag_case_insensitive(self):
        """Test that tag parsing is case-insensitive."""
        docstring = "@ATHENA: abc123def456"
        result = PythonParser.parse_athena_tag(docstring)
        assert result == "abc123def456"

    def test_parse_tag_not_found(self):
        """Test returns None when no tag present."""
        docstring = "Just a regular docstring."
        result = PythonParser.parse_athena_tag(docstring)
        assert result is None

    def test_parse_tag_empty_docstring(self):
        """Test returns None for empty docstring."""
        assert PythonParser.parse_athena_tag("") is None
        assert PythonParser.parse_athena_tag(None) is None

    def test_parse_tag_malformed(self):
        """Test returns None for malformed tags."""
        # Too short
        docstring1 = "@athena: abc123"
        assert PythonParser.parse_athena_tag(docstring1) is None

        # Non-hex characters
        docstring2 = "@athena: xyzabc123456"
        assert PythonParser.parse_athena_tag(docstring2) is None

    def test_parse_tag_at_start(self):
        """Test parsing tag at start of docstring."""
        docstring = "@athena: a1b2c3d4e5f6\nRest of docstring."
        result = PythonParser.parse_athena_tag(docstring)
        assert result == "a1b2c3d4e5f6"

    def test_parse_tag_at_end(self):
        """Test parsing tag at end of docstring."""
        docstring = "Function summary.\n@athena: fedcba987654"
        result = PythonParser.parse_athena_tag(docstring)
        assert result == "fedcba987654"


class TestUpdateAthenaTag:
    """Tests for PythonParser.update_athena_tag."""

    def test_insert_tag_in_empty_docstring(self):
        """Test inserting tag when docstring is empty."""
        result = PythonParser.update_athena_tag("", "abc123def456")
        assert result == "@athena: abc123def456"

    def test_insert_tag_in_none_docstring(self):
        """Test inserting tag when docstring is None."""
        result = PythonParser.update_athena_tag(None, "abc123def456")
        assert result == "@athena: abc123def456"

    def test_update_existing_tag(self):
        """Test updating existing tag."""
        docstring = """Function summary.
        @athena: oldoldoldold
        """
        result = PythonParser.update_athena_tag(docstring, "newnewnewnew")
        assert "@athena: newnewnewnew" in result
        assert "oldoldoldold" not in result
        assert "Function summary" in result

    def test_append_tag_to_docstring(self):
        """Test appending tag when none exists."""
        docstring = "Function summary."
        result = PythonParser.update_athena_tag(docstring, "abc123def456")
        assert "Function summary" in result
        assert "@athena: abc123def456" in result

    def test_append_tag_preserves_content(self):
        """Test that appending tag preserves existing content."""
        docstring = """This is a multi-line
        docstring with details.
        """
        result = PythonParser.update_athena_tag(docstring, "abc123def456")
        assert "multi-line" in result
        assert "with details" in result
        assert "@athena: abc123def456" in result

    def test_update_tag_case_insensitive(self):
        """Test that update works with case variations."""
        docstring = "@ATHENA: oldoldoldold"
        result = PythonParser.update_athena_tag(docstring, "newnewnewnew")
        assert "@athena: newnewnewnew" in result.lower()
        assert "oldoldoldold" not in result

    def test_append_tag_with_newline(self):
        """Test appending when docstring ends with newline."""
        docstring = "Summary.\n"
        result = PythonParser.update_athena_tag(docstring, "abc123def456")
        assert result == "Summary.\n@athena: abc123def456"

    def test_append_tag_without_newline(self):
        """Test appending when docstring doesn't end with newline."""
        docstring = "Summary."
        result = PythonParser.update_athena_tag(docstring, "abc123def456")
        assert result == "Summary.\n@athena: abc123def456"


class TestValidateAthenaTag:
    """Tests for PythonParser.validate_athena_tag."""

    def test_validate_correct_tag(self):
        """Test validation of correct 12-char hex tag."""
        assert PythonParser.validate_athena_tag("abc123def456") is True
        assert PythonParser.validate_athena_tag("000000000000") is True
        assert PythonParser.validate_athena_tag("fffFFFfffFFF") is True

    def test_validate_empty_tag(self):
        """Test validation of empty tag."""
        assert PythonParser.validate_athena_tag("") is False
        assert PythonParser.validate_athena_tag(None) is False

    def test_validate_wrong_length(self):
        """Test validation fails for wrong length."""
        assert PythonParser.validate_athena_tag("abc") is False  # Too short
        assert PythonParser.validate_athena_tag("abc123def456789") is False  # Too long

    def test_validate_non_hex(self):
        """Test validation fails for non-hex characters."""
        assert PythonParser.validate_athena_tag("ghijklmnopqr") is False
        assert PythonParser.validate_athena_tag("abc123def45@") is False

    def test_validate_with_spaces(self):
        """Test validation fails if tag contains spaces."""
        assert PythonParser.validate_athena_tag("abc 123def45") is False


class TestUpdateDocstringInSource:
    """Tests for update_docstring_in_source."""

    def test_update_existing_docstring(self):
        """Test updating existing docstring."""
        source = '''def foo():
    """Old docstring."""
    return 1
'''
        location = Location(start=0, end=2)
        new_docstring = "New docstring.\n@athena: abc123def456"

        result = update_docstring_in_source(source, location, new_docstring)

        assert "New docstring" in result
        assert "@athena: abc123def456" in result
        assert "Old docstring" not in result
        assert "return 1" in result

    def test_update_multiline_docstring(self):
        """Test updating multi-line docstring."""
        source = '''def foo():
    """
    Old multi-line
    docstring.
    """
    return 1
'''
        location = Location(start=0, end=5)
        new_docstring = "New summary.\n@athena: abc123def456"

        result = update_docstring_in_source(source, location, new_docstring)

        assert "New summary" in result
        assert "@athena: abc123def456" in result
        assert "Old multi-line" not in result

    def test_insert_docstring_when_missing(self):
        """Test inserting docstring when entity has none."""
        source = '''def foo():
    return 1
'''
        location = Location(start=0, end=1)
        new_docstring = "@athena: abc123def456"

        result = update_docstring_in_source(source, location, new_docstring)

        assert "@athena: abc123def456" in result
        assert "return 1" in result
        # Check that docstring is inserted in correct position
        lines = result.splitlines()
        assert '"""' in lines[1]  # Docstring starts on line after def

    def test_preserve_indentation_function(self):
        """Test that function indentation is preserved."""
        source = '''def foo():
    """Old."""
    return 1
'''
        location = Location(start=0, end=2)
        new_docstring = "New."

        result = update_docstring_in_source(source, location, new_docstring)

        # Check proper indentation
        lines = result.splitlines()
        assert lines[1].startswith("    ")  # Docstring indent
        assert "return 1" in result

    def test_preserve_indentation_method(self):
        """Test that method indentation (nested) is preserved."""
        source = '''class Foo:
    def bar(self):
        """Old."""
        return 1
'''
        location = Location(start=1, end=3)
        new_docstring = "New method doc."

        result = update_docstring_in_source(source, location, new_docstring)

        # Check proper nested indentation
        lines = result.splitlines()
        assert "New method doc" in result
        # Method docstring should have 8 spaces (2 levels)
        assert '        """' in result

    def test_update_class_docstring(self):
        """Test updating class docstring."""
        source = '''class Foo:
    """Old class doc."""
    def bar(self):
        pass
'''
        location = Location(start=0, end=3)
        new_docstring = "New class doc.\n@athena: abc123def456"

        result = update_docstring_in_source(source, location, new_docstring)

        assert "New class doc" in result
        assert "@athena: abc123def456" in result
        assert "Old class doc" not in result
        assert "def bar" in result

    def test_handle_single_quote_docstring(self):
        """Test handling single-quote docstrings."""
        source = """def foo():
    '''Old docstring.'''
    return 1
"""
        location = Location(start=0, end=2)
        new_docstring = "New docstring."

        result = update_docstring_in_source(source, location, new_docstring)

        assert "New docstring" in result
        assert "Old docstring" not in result
        # Updated to double quotes
        assert '"""' in result

    def test_invalid_location_raises_error(self):
        """Test that invalid location raises ValueError."""
        source = "def foo():\n    pass\n"
        invalid_location = Location(start=10, end=20)

        with pytest.raises(ValueError):
            update_docstring_in_source(source, invalid_location, "New doc")

    def test_preserve_empty_lines_in_docstring(self):
        """Test that empty lines in new docstring are preserved."""
        source = '''def foo():
    """Old."""
    return 1
'''
        location = Location(start=0, end=2)
        new_docstring = "First line.\n\nThird line after blank."

        result = update_docstring_in_source(source, location, new_docstring)

        assert "First line" in result
        assert "Third line after blank" in result
        # Should have preserved the blank line
        lines = result.splitlines()
        # Find the blank line between content
        assert any(line.strip() == "" for line in lines[2:5])
