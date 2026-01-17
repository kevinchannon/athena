"""Tests for module-level docstring operations."""

import pytest

from athena.module_docstring_updater import (
    detect_file_header,
    extract_module_docstring,
    update_module_docstring,
)


class TestDetectFileHeader:
    """Tests for detect_file_header function."""

    def test_detect_shebang_present(self):
        """Test detection of shebang line."""
        source = "#!/usr/bin/env python3\nimport sys\n"
        shebang, encoding, end_idx = detect_file_header(source)

        assert shebang == "#!/usr/bin/env python3\n"
        assert encoding is None
        assert end_idx == 1

    def test_detect_encoding_present(self):
        """Test detection of encoding declaration."""
        source = "# -*- coding: utf-8 -*-\nimport sys\n"
        shebang, encoding, end_idx = detect_file_header(source)

        assert shebang is None
        assert encoding == "# -*- coding: utf-8 -*-\n"
        assert end_idx == 1

    def test_detect_both_shebang_and_encoding(self):
        """Test detection when both shebang and encoding are present."""
        source = "#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\nimport sys\n"
        shebang, encoding, end_idx = detect_file_header(source)

        assert shebang == "#!/usr/bin/env python3\n"
        assert encoding == "# -*- coding: utf-8 -*-\n"
        assert end_idx == 2

    def test_detect_neither_shebang_nor_encoding(self):
        """Test when neither shebang nor encoding is present."""
        source = "import sys\n\ndef foo():\n    pass\n"
        shebang, encoding, end_idx = detect_file_header(source)

        assert shebang is None
        assert encoding is None
        assert end_idx == 0

    def test_detect_empty_file(self):
        """Test with empty file."""
        shebang, encoding, end_idx = detect_file_header("")

        assert shebang is None
        assert encoding is None
        assert end_idx == 0

    def test_detect_encoding_vim_style(self):
        """Test detection of vim-style encoding."""
        source = "# vim: set fileencoding=utf-8 :\nimport sys\n"
        shebang, encoding, end_idx = detect_file_header(source)

        assert shebang is None
        assert encoding == "# vim: set fileencoding=utf-8 :\n"
        assert end_idx == 1

    def test_detect_encoding_emacs_style(self):
        """Test detection of emacs-style encoding."""
        source = "# -*- coding: latin-1 -*-\nimport sys\n"
        shebang, encoding, end_idx = detect_file_header(source)

        assert shebang is None
        assert encoding == "# -*- coding: latin-1 -*-\n"
        assert end_idx == 1


class TestExtractModuleDocstring:
    """Tests for extract_module_docstring function."""

    def test_extract_module_docstring_present(self):
        """Test extracting existing module docstring."""
        source = '"""This is a module docstring."""\nimport sys\n'
        docstring = extract_module_docstring(source)

        assert docstring == "This is a module docstring."

    def test_extract_module_docstring_absent(self):
        """Test when no module docstring is present."""
        source = "import sys\n\ndef foo():\n    pass\n"
        docstring = extract_module_docstring(source)

        assert docstring is None

    def test_extract_module_docstring_after_shebang(self):
        """Test extracting docstring that comes after shebang."""
        source = '#!/usr/bin/env python3\n"""Module doc."""\nimport sys\n'
        docstring = extract_module_docstring(source)

        assert docstring == "Module doc."

    def test_extract_multiline_docstring(self):
        """Test extracting multi-line module docstring."""
        source = '''"""
This is a multi-line
module docstring.
"""
import sys
'''
        docstring = extract_module_docstring(source)

        assert "multi-line" in docstring
        assert "module docstring" in docstring

    def test_extract_empty_file(self):
        """Test with empty file."""
        docstring = extract_module_docstring("")

        assert docstring is None

    def test_extract_single_quote_docstring(self):
        """Test extracting single-quote docstring."""
        source = "'''\nModule docstring.\n'''\nimport sys\n"
        docstring = extract_module_docstring(source)

        assert docstring == "Module docstring."

    def test_extract_invalid_syntax(self):
        """Test with invalid Python syntax."""
        source = "def foo(\nimport sys"
        docstring = extract_module_docstring(source)

        assert docstring is None


class TestUpdateModuleDocstring:
    """Tests for update_module_docstring function."""

    def test_update_module_docstring_no_existing(self):
        """Test inserting docstring when none exists."""
        source = "import sys\n\ndef foo():\n    pass\n"
        new_docstring = "New module docstring.\n@athena: abc123def456"

        result = update_module_docstring(source, new_docstring)

        assert "New module docstring" in result
        assert "@athena: abc123def456" in result
        assert "import sys" in result
        assert "def foo" in result

    def test_update_module_docstring_replace_existing(self):
        """Test replacing existing module docstring."""
        source = '"""Old docstring."""\nimport sys\n'
        new_docstring = "New module docstring.\n@athena: abc123def456"

        result = update_module_docstring(source, new_docstring)

        assert "New module docstring" in result
        assert "@athena: abc123def456" in result
        assert "Old docstring" not in result
        assert "import sys" in result

    def test_update_module_docstring_preserve_shebang(self):
        """Test that shebang is preserved when updating docstring."""
        source = '#!/usr/bin/env python3\n"""Old docstring."""\nimport sys\n'
        new_docstring = "New docstring with tag.\n@athena: abc123def456"

        result = update_module_docstring(source, new_docstring)

        lines = result.splitlines()
        assert lines[0] == "#!/usr/bin/env python3"
        assert "New docstring with tag" in result
        assert "@athena: abc123def456" in result
        assert "Old docstring" not in result

    def test_update_module_docstring_preserve_encoding(self):
        """Test that encoding declaration is preserved."""
        source = '# -*- coding: utf-8 -*-\n"""Old docstring."""\nimport sys\n'
        new_docstring = "New docstring.\n@athena: abc123def456"

        result = update_module_docstring(source, new_docstring)

        lines = result.splitlines()
        assert lines[0] == "# -*- coding: utf-8 -*-"
        assert "New docstring" in result
        assert "@athena: abc123def456" in result

    def test_update_module_docstring_preserve_both_headers(self):
        """Test preserving both shebang and encoding."""
        source = '#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n"""Old docstring."""\nimport sys\n'
        new_docstring = "New docstring.\n@athena: abc123def456"

        result = update_module_docstring(source, new_docstring)

        lines = result.splitlines()
        assert lines[0] == "#!/usr/bin/env python3"
        assert lines[1] == "# -*- coding: utf-8 -*-"
        assert "New docstring" in result
        assert "@athena: abc123def456" in result
        assert "import sys" in result

    def test_update_empty_module(self):
        """Test updating docstring in empty module."""
        source = ""
        new_docstring = "Module docstring.\n@athena: abc123def456"

        result = update_module_docstring(source, new_docstring)

        assert "Module docstring" in result
        assert "@athena: abc123def456" in result

    def test_update_module_only_shebang(self):
        """Test updating module with only shebang, no code."""
        source = "#!/usr/bin/env python3\n"
        new_docstring = "New module.\n@athena: abc123def456"

        result = update_module_docstring(source, new_docstring)

        lines = result.splitlines()
        assert lines[0] == "#!/usr/bin/env python3"
        assert "New module" in result
        assert "@athena: abc123def456" in result

    def test_update_preserves_code_after_docstring(self):
        """Test that all code after docstring is preserved."""
        source = '''"""Old docstring."""

import sys
import os

def foo():
    """Function docstring."""
    return 1

class Bar:
    """Class docstring."""
    pass
'''
        new_docstring = "New module docstring.\n@athena: abc123def456"

        result = update_module_docstring(source, new_docstring)

        assert "New module docstring" in result
        assert "@athena: abc123def456" in result
        assert "Old docstring" not in result
        assert "import sys" in result
        assert "import os" in result
        assert "def foo():" in result
        assert "class Bar:" in result
        # Function and class docstrings should be preserved
        assert "Function docstring" in result
        assert "Class docstring" in result

    def test_update_multiline_existing_docstring(self):
        """Test replacing multi-line existing docstring."""
        source = '''"""
This is a long
multi-line docstring
with several lines.
"""

import sys
'''
        new_docstring = "Short new docstring.\n@athena: abc123def456"

        result = update_module_docstring(source, new_docstring)

        assert "Short new docstring" in result
        assert "@athena: abc123def456" in result
        assert "long" not in result
        assert "several lines" not in result
        assert "import sys" in result
