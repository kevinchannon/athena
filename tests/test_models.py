from dataclasses import asdict

from athena.models import Entity, Location


def test_location_creation():
    location = Location(start=10, end=20)
    assert location.start == 10
    assert location.end == 20


def test_entity_creation():
    location = Location(start=5, end=15)
    entity = Entity(kind="function", path="src/example.py", extent=location)

    assert entity.kind == "function"
    assert entity.path == "src/example.py"
    assert entity.extent == location


def test_entity_to_dict():
    location = Location(start=10, end=20)
    entity = Entity(kind="class", path="src/models.py", extent=location, name="MyClass")

    entity_dict = asdict(entity)

    # Internal representation includes name
    assert entity_dict == {
        "kind": "class",
        "path": "src/models.py",
        "extent": {"start": 10, "end": 20},
        "name": "MyClass"
    }


def test_entity_to_dict_for_json_output():
    location = Location(start=10, end=20)
    entity = Entity(kind="class", path="src/models.py", extent=location, name="MyClass")

    entity_dict = asdict(entity)
    # Remove name for JSON output (name is only for internal filtering)
    del entity_dict["name"]

    assert entity_dict == {
        "kind": "class",
        "path": "src/models.py",
        "extent": {"start": 10, "end": 20}
    }
