from abc import ABC, abstractmethod

from athena.models import ClassInfo, Entity, FunctionInfo, MethodInfo, ModuleInfo


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

    @abstractmethod
    def extract_entity_info(
        self,
        source_code: str,
        file_path: str,
        entity_name: str | None = None
    ) -> FunctionInfo | ClassInfo | MethodInfo | ModuleInfo | None:
        """Extract detailed information about a specific entity.

        Args:
            source_code: The source code to parse
            file_path: Relative path to the file (for EntityInfo.path)
            entity_name: Name of entity to find, or None for module-level

        Returns:
            EntityInfo object, or None if not found
        """
        pass
