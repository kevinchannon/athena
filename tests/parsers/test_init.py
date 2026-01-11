from pathlib import Path

from athena.parsers import get_parser_for_file
from athena.parsers.python_parser import PythonParser


def test_get_parser_for_python_file():
    parser = get_parser_for_file(Path("test.py"))

    assert parser is not None
    assert isinstance(parser, PythonParser)


def test_get_parser_for_uppercase_extension():
    parser = get_parser_for_file(Path("test.PY"))

    assert parser is not None
    assert isinstance(parser, PythonParser)


def test_get_parser_for_unsupported_file():
    parser = get_parser_for_file(Path("test.txt"))

    assert parser is None


def test_get_parser_for_javascript_file():
    parser = get_parser_for_file(Path("test.js"))

    # JavaScript not yet supported
    assert parser is None


def test_get_parser_for_typescript_file():
    parser = get_parser_for_file(Path("test.ts"))

    # TypeScript not yet supported
    assert parser is None
