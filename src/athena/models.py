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
