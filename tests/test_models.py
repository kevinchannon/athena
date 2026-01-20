from dataclasses import asdict

from athena.models import (
    ClassInfo,
    Entity,
    EntityStatus,
    FunctionInfo,
    Location,
    MethodInfo,
    ModuleInfo,
    PackageInfo,
    Parameter,
    SearchResult,
    Signature,
)


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


def test_function_info_creation():
    location = Location(start=10, end=20)
    params = [Parameter(name="token", type="str", default='"abc"')]
    sig = Signature(name="validate", args=params, return_type="bool")
    info = FunctionInfo(
        path="src/auth.py",
        extent=location,
        sig=sig,
        summary="Validates token."
    )

    assert info.path == "src/auth.py"
    assert info.extent == location
    assert info.sig == sig
    assert info.summary == "Validates token."


def test_function_info_without_summary():
    location = Location(start=1, end=10)
    sig = Signature(name="func", args=[])
    info = FunctionInfo(path="src/utils.py", extent=location, sig=sig)

    assert info.path == "src/utils.py"
    assert info.sig == sig
    assert info.summary is None


def test_function_info_to_dict():
    location = Location(start=88, end=105)
    params = [Parameter(name="token", type="str", default='"112312daea1313"')]
    sig = Signature(name="validateSession", args=params, return_type="bool")
    info = FunctionInfo(
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


def test_class_info_creation():
    location = Location(start=5, end=25)
    methods = ["add(self, x: int, y: int) -> int", "subtract(self, x: int, y: int) -> int"]
    info = ClassInfo(
        path="src/calculator.py",
        extent=location,
        methods=methods,
        summary="Calculator class."
    )

    assert info.path == "src/calculator.py"
    assert info.extent == location
    assert info.methods == methods
    assert info.summary == "Calculator class."


def test_class_info_without_methods():
    location = Location(start=5, end=10)
    info = ClassInfo(
        path="src/empty.py",
        extent=location,
        methods=[],
        summary="Empty class."
    )

    assert info.methods == []


def test_class_info_to_dict():
    location = Location(start=5, end=25)
    methods = ["add(self, x: int) -> int"]
    info = ClassInfo(
        path="src/calc.py",
        extent=location,
        methods=methods,
        summary="Calculator."
    )

    info_dict = asdict(info)

    assert info_dict == {
        "path": "src/calc.py",
        "extent": {"start": 5, "end": 25},
        "methods": ["add(self, x: int) -> int"],
        "summary": "Calculator."
    }


def test_method_info_creation():
    location = Location(start=12, end=15)
    params = [Parameter(name="self"), Parameter(name="x", type="int")]
    sig = Signature(name="add", args=params, return_type="int")
    info = MethodInfo(
        name="Calculator.add",
        path="src/calc.py",
        extent=location,
        sig=sig,
        summary="Add method."
    )

    assert info.name == "Calculator.add"
    assert info.path == "src/calc.py"
    assert info.sig == sig
    assert info.summary == "Add method."


def test_method_info_to_dict():
    location = Location(start=12, end=15)
    params = [Parameter(name="self"), Parameter(name="x", type="int")]
    sig = Signature(name="add", args=params, return_type="int")
    info = MethodInfo(
        name="Calculator.add",
        path="src/calc.py",
        extent=location,
        sig=sig,
        summary="Add method."
    )

    info_dict = asdict(info)

    assert info_dict["name"] == "Calculator.add"
    assert info_dict["sig"]["name"] == "add"


def test_module_info_creation():
    location = Location(start=0, end=50)
    info = ModuleInfo(
        path="src/models.py",
        extent=location,
        summary="Data models module."
    )

    assert info.path == "src/models.py"
    assert info.extent == location
    assert info.summary == "Data models module."


def test_module_info_without_summary():
    location = Location(start=0, end=20)
    info = ModuleInfo(path="src/utils.py", extent=location)

    assert info.summary is None


def test_module_info_to_dict():
    location = Location(start=0, end=50)
    info = ModuleInfo(
        path="src/models.py",
        extent=location,
        summary="Module docstring."
    )

    info_dict = asdict(info)

    assert info_dict == {
        "path": "src/models.py",
        "extent": {"start": 0, "end": 50},
        "summary": "Module docstring."
    }


def test_package_info_creation():
    info = PackageInfo(
        path="src/mypackage",
        summary="Test package."
    )

    assert info.path == "src/mypackage"
    assert info.summary == "Test package."


def test_package_info_without_summary():
    info = PackageInfo(path="src/mypackage")

    assert info.summary is None


def test_package_info_to_dict():
    info = PackageInfo(
        path="src/mypackage",
        summary="Package docstring."
    )

    info_dict = asdict(info)

    assert info_dict == {
        "path": "src/mypackage",
        "summary": "Package docstring."
    }


def test_package_info_no_extent():
    """Test that PackageInfo does not have extent field."""
    info = PackageInfo(path="src/mypackage", summary="Test.")

    # PackageInfo should not have extent attribute
    assert not hasattr(info, 'extent')
    assert not hasattr(info, 'sig')


def test_entity_status_creation():
    status = EntityStatus(
        kind="function",
        path="src/example.py:my_func",
        extent="10-20",
        recorded_hash="abc123",
        calculated_hash="def456"
    )

    assert status.kind == "function"
    assert status.path == "src/example.py:my_func"
    assert status.extent == "10-20"
    assert status.recorded_hash == "abc123"
    assert status.calculated_hash == "def456"


def test_entity_status_no_recorded_hash():
    status = EntityStatus(
        kind="class",
        path="src/models.py:MyClass",
        extent="5-15",
        recorded_hash=None,
        calculated_hash="xyz789"
    )

    assert status.recorded_hash is None
    assert status.calculated_hash == "xyz789"


def test_entity_status_module_no_extent():
    status = EntityStatus(
        kind="module",
        path="src/utils.py",
        extent="",
        recorded_hash="old123",
        calculated_hash="new456"
    )

    assert status.extent == ""


def test_search_result_creation():
    location = Location(start=10, end=25)
    result = SearchResult(
        kind="function",
        path="src/auth.py",
        extent=location,
        summary="Validates JWT token and returns user object."
    )

    assert result.kind == "function"
    assert result.path == "src/auth.py"
    assert result.extent == location
    assert result.summary == "Validates JWT token and returns user object."


def test_search_result_to_dict():
    location = Location(start=15, end=30)
    result = SearchResult(
        kind="class",
        path="src/models.py",
        extent=location,
        summary="User authentication model."
    )

    result_dict = asdict(result)

    assert result_dict == {
        "kind": "class",
        "path": "src/models.py",
        "extent": {"start": 15, "end": 30},
        "summary": "User authentication model."
    }


def test_search_result_multiline_summary():
    location = Location(start=5, end=20)
    result = SearchResult(
        kind="method",
        path="src/service.py",
        extent=location,
        summary="Process user request.\n\nThis method handles authentication and validation."
    )

    assert result.summary == "Process user request.\n\nThis method handles authentication and validation."
    assert "\n\n" in result.summary
