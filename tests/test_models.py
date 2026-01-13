from dataclasses import asdict

from athena.models import Entity, EntityInfo, Location, Parameter, Signature


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


def test_parameter_creation():
    param = Parameter(name="x", type="int", default="5")
    assert param.name == "x"
    assert param.type == "int"
    assert param.default == "5"


def test_parameter_without_type_or_default():
    param = Parameter(name="x")
    assert param.name == "x"
    assert param.type is None
    assert param.default is None


def test_signature_creation():
    params = [
        Parameter(name="x", type="int", default="5"),
        Parameter(name="y", type="str")
    ]
    sig = Signature(name="foo", args=params, return_type="bool")
    assert sig.name == "foo"
    assert len(sig.args) == 2
    assert sig.return_type == "bool"


def test_signature_without_return_type():
    sig = Signature(name="bar", args=[])
    assert sig.name == "bar"
    assert sig.args == []
    assert sig.return_type is None


def test_entity_info_full():
    location = Location(start=10, end=20)
    params = [Parameter(name="token", type="str", default='"abc"')]
    sig = Signature(name="validate", args=params, return_type="bool")
    info = EntityInfo(
        path="src/auth.py",
        extent=location,
        sig=sig,
        summary="Validates token."
    )

    assert info.path == "src/auth.py"
    assert info.extent == location
    assert info.sig == sig
    assert info.summary == "Validates token."


def test_entity_info_without_signature():
    location = Location(start=5, end=15)
    info = EntityInfo(
        path="src/models.py",
        extent=location,
        summary="Data models module."
    )

    assert info.path == "src/models.py"
    assert info.extent == location
    assert info.sig is None
    assert info.summary == "Data models module."


def test_entity_info_without_summary():
    location = Location(start=1, end=10)
    sig = Signature(name="func", args=[])
    info = EntityInfo(path="src/utils.py", extent=location, sig=sig)

    assert info.path == "src/utils.py"
    assert info.sig == sig
    assert info.summary is None


def test_entity_info_to_dict():
    location = Location(start=88, end=105)
    params = [Parameter(name="token", type="str", default='"112312daea1313"')]
    sig = Signature(name="validateSession", args=params, return_type="bool")
    info = EntityInfo(
        path="src/auth/session.py",
        extent=location,
        sig=sig,
        summary="Validates JWT token and returns user object."
    )

    info_dict = asdict(info)

    assert info_dict == {
        "path": "src/auth/session.py",
        "extent": {"start": 88, "end": 105},
        "sig": {
            "name": "validateSession",
            "args": [
                {"name": "token", "type": "str", "default": '"112312daea1313"'}
            ],
            "return_type": "bool"
        },
        "summary": "Validates JWT token and returns user object."
    }


def test_entity_info_to_dict_without_summary():
    location = Location(start=10, end=20)
    sig = Signature(name="func", args=[])
    info = EntityInfo(path="src/utils.py", extent=location, sig=sig)

    info_dict = asdict(info)

    # When summary is None, asdict includes it with None value
    # We'll need to filter this out when generating JSON
    assert info_dict["summary"] is None
