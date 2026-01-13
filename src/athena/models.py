from dataclasses import dataclass


@dataclass
class Location:
    """Represents a line range in a source file (0-indexed, inclusive)."""
    start: int
    end: int


@dataclass
class Entity:
    """Represents a code entity (function, class, or method) found in a file."""
    kind: str
    path: str
    extent: Location
    name: str = ""  # Entity name (for filtering, not included in JSON output)


@dataclass
class Parameter:
    """Represents a function/method parameter."""
    name: str
    type: str | None = None  # None if no type hint
    default: str | None = None  # None if no default value


@dataclass
class Signature:
    """Represents a function/method signature."""
    name: str
    args: list[Parameter]
    return_type: str | None = None  # None if no return annotation


@dataclass
class EntityInfo:
    """Detailed information about a code entity."""
    path: str
    extent: Location
    sig: Signature | None = None  # None for modules/classes without callable signature
    summary: str | None = None  # Docstring, None if absent
