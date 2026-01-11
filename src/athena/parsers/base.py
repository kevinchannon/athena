from abc import ABC, abstractmethod

from athena.models import Entity


class BaseParser(ABC):
    """Abstract base class for language-specific entity parsers."""

    @abstractmethod
    def extract_entities(self, source_code: str, file_path: str) -> list[Entity]:
        """Extract all entities (functions, classes, methods) from source code.

        Args:
            source_code: The source code to parse
            file_path: Relative path to the file (for Entity.path)

        Returns:
            List of Entity objects found in the source code
        """
        pass
