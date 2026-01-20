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
class FunctionInfo:
    """Information about a function."""
    path: str
    extent: Location
    sig: Signature
    summary: str | None = None


@dataclass
class ClassInfo:
    """Information about a class."""
    path: str
    extent: Location
    methods: list[str]  # Formatted method signatures
    summary: str | None = None


@dataclass
class MethodInfo:
    """Information about a method."""
    name: str  # Qualified name: "ClassName.method_name"
    path: str
    extent: Location
    sig: Signature
    summary: str | None = None


@dataclass
class ModuleInfo:
    """Information about a module."""
    path: str
    extent: Location
    summary: str | None = None


@dataclass
class PackageInfo:
    """Information about a package (directory with __init__.py)."""
    path: str
    summary: str | None = None


@dataclass
class EntityStatus:
    """Status information for an entity's hash synchronization state."""
    kind: str
    path: str
    extent: Location  # Line range for the entity
    recorded_hash: str | None  # Hash from docstring, None if no hash
    calculated_hash: str  # Hash computed from AST


@dataclass
class SearchResult:
    """Represents a search result with entity details and docstring summary."""
    kind: str
    path: str
    extent: Location
    summary: str


# Union type for entity info
EntityInfo = FunctionInfo | ClassInfo | MethodInfo | ModuleInfo | PackageInfo
