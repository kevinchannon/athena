import pytest

from athena.parsers.base import BaseParser


def test_cannot_instantiate_base_parser():
    with pytest.raises(TypeError) as exc_info:
        BaseParser()

    assert "abstract" in str(exc_info.value).lower()


def test_subclass_must_implement_extract_entities():
    class IncompleteParser(BaseParser):
        pass

    with pytest.raises(TypeError) as exc_info:
        IncompleteParser()

    assert "extract_entities" in str(exc_info.value)
