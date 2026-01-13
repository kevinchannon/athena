from athena.models import ClassInfo, ModuleInfo, Parameter
from athena.parsers.python_parser import PythonParser


def test_extract_simple_function():
    source = """def hello():
    print("world")
"""
    parser = PythonParser()

    entities = parser.extract_entities(source, "test.py")

    assert len(entities) == 1
    assert entities[0].kind == "function"
    assert entities[0].path == "test.py"
    assert entities[0].extent.start == 0
    assert entities[0].extent.end == 1


def test_extract_multiple_functions():
    source = """def first():
    pass

def second():
    pass

def third():
    pass
"""
    parser = PythonParser()

    entities = parser.extract_entities(source, "test.py")

    assert len(entities) == 3
    assert all(e.kind == "function" for e in entities)


def test_extract_function_with_arguments():
    source = """def calculate(x, y):
    return x + y
"""
    parser = PythonParser()

    entities = parser.extract_entities(source, "test.py")

    assert len(entities) == 1
    assert entities[0].kind == "function"


def test_extract_function_verifies_line_numbers_are_zero_indexed():
    source = """# This is a comment on line 0
def my_function():
    pass
"""
    parser = PythonParser()

    entities = parser.extract_entities(source, "test.py")

    assert len(entities) == 1
    assert entities[0].extent.start == 1
    assert entities[0].extent.end == 2


def test_extract_function_multiline():
    source = """def long_function(
    arg1,
    arg2,
    arg3
):
    result = arg1 + arg2 + arg3
    return result
"""
    parser = PythonParser()

    entities = parser.extract_entities(source, "test.py")

    assert len(entities) == 1
    assert entities[0].extent.start == 0
    assert entities[0].extent.end == 6


def test_extract_simple_class():
    source = """class MyClass:
    pass
"""
    parser = PythonParser()

    entities = parser.extract_entities(source, "test.py")

    assert len(entities) == 1
    assert entities[0].kind == "class"
    assert entities[0].path == "test.py"
    assert entities[0].extent.start == 0
    assert entities[0].extent.end == 1


def test_extract_class_with_methods():
    source = """class Calculator:
    def add(self, x, y):
        return x + y
"""
    parser = PythonParser()

    entities = parser.extract_entities(source, "test.py")

    # Should find the class (methods will be extracted in next commit)
    classes = [e for e in entities if e.kind == "class"]
    assert len(classes) == 1
    assert classes[0].extent.start == 0
    assert classes[0].extent.end == 2


def test_extract_multiple_classes():
    source = """class First:
    pass

class Second:
    pass
"""
    parser = PythonParser()

    entities = parser.extract_entities(source, "test.py")

    classes = [e for e in entities if e.kind == "class"]
    assert len(classes) == 2


def test_extract_classes_and_functions():
    source = """def helper():
    pass

class MyClass:
    pass

def another_function():
    pass
"""
    parser = PythonParser()

    entities = parser.extract_entities(source, "test.py")

    functions = [e for e in entities if e.kind == "function"]
    classes = [e for e in entities if e.kind == "class"]

    assert len(functions) == 2
    assert len(classes) == 1


def test_extract_method():
    source = """class Calculator:
    def add(self, x, y):
        return x + y
"""
    parser = PythonParser()

    entities = parser.extract_entities(source, "test.py")

    methods = [e for e in entities if e.kind == "method"]
    assert len(methods) == 1
    assert methods[0].extent.start == 1
    assert methods[0].extent.end == 2


def test_extract_multiple_methods():
    source = """class MathOps:
    def add(self, x, y):
        return x + y

    def subtract(self, x, y):
        return x - y

    def multiply(self, x, y):
        return x * y
"""
    parser = PythonParser()

    entities = parser.extract_entities(source, "test.py")

    methods = [e for e in entities if e.kind == "method"]
    assert len(methods) == 3


def test_extract_nested_method():
    source = """class Outer:
    def outer_method(self):
        def inner_function():
            pass
        return inner_function
"""
    parser = PythonParser()

    entities = parser.extract_entities(source, "test.py")

    methods = [e for e in entities if e.kind == "method"]
    # Only the method should be extracted, not nested functions
    assert len(methods) == 1
    assert methods[0].extent.start == 1


def test_extract_class_with_methods_and_functions():
    source = """def standalone_function():
    pass

class MyClass:
    def method_one(self):
        pass

    def method_two(self):
        pass

def another_function():
    pass
"""
    parser = PythonParser()

    entities = parser.extract_entities(source, "test.py")

    functions = [e for e in entities if e.kind == "function"]
    classes = [e for e in entities if e.kind == "class"]
    methods = [e for e in entities if e.kind == "method"]

    assert len(functions) == 2
    assert len(classes) == 1
    assert len(methods) == 2


def test_extract_docstring_from_function():
    source = '''def hello():
    """This is a docstring."""
    print("world")
'''
    parser = PythonParser()
    tree = parser.parser.parse(bytes(source, "utf8"))
    # Get the function node
    func_node = tree.root_node.children[0]

    docstring = parser._extract_docstring(func_node, source)

    assert docstring == "This is a docstring."


def test_extract_docstring_from_function_without_docstring():
    source = """def hello():
    print("world")
"""
    parser = PythonParser()
    tree = parser.parser.parse(bytes(source, "utf8"))
    func_node = tree.root_node.children[0]

    docstring = parser._extract_docstring(func_node, source)

    assert docstring is None


def test_extract_multiline_docstring():
    source = '''def hello():
    """This is a multiline docstring.

    It has multiple lines.
    And even more lines.
    """
    print("world")
'''
    parser = PythonParser()
    tree = parser.parser.parse(bytes(source, "utf8"))
    func_node = tree.root_node.children[0]

    docstring = parser._extract_docstring(func_node, source)

    expected = """This is a multiline docstring.

    It has multiple lines.
    And even more lines.
    """
    assert docstring == expected


def test_extract_docstring_from_class():
    source = '''class MyClass:
    """This is a class docstring."""
    pass
'''
    parser = PythonParser()
    tree = parser.parser.parse(bytes(source, "utf8"))
    class_node = tree.root_node.children[0]

    docstring = parser._extract_docstring(class_node, source)

    assert docstring == "This is a class docstring."


def test_extract_docstring_from_class_without_docstring():
    source = """class MyClass:
    pass
"""
    parser = PythonParser()
    tree = parser.parser.parse(bytes(source, "utf8"))
    class_node = tree.root_node.children[0]

    docstring = parser._extract_docstring(class_node, source)

    assert docstring is None


def test_extract_module_level_docstring():
    source = '''"""This is a module-level docstring."""

def some_function():
    pass
'''
    parser = PythonParser()
    tree = parser.parser.parse(bytes(source, "utf8"))

    docstring = parser._extract_docstring(tree.root_node, source)

    assert docstring == "This is a module-level docstring."


def test_extract_module_level_docstring_not_present():
    source = """def some_function():
    pass
"""
    parser = PythonParser()
    tree = parser.parser.parse(bytes(source, "utf8"))

    docstring = parser._extract_docstring(tree.root_node, source)

    assert docstring is None


def test_extract_docstring_with_single_quotes():
    source = """def hello():
    'This is a docstring with single quotes.'
    print("world")
"""
    parser = PythonParser()
    tree = parser.parser.parse(bytes(source, "utf8"))
    func_node = tree.root_node.children[0]

    docstring = parser._extract_docstring(func_node, source)

    assert docstring == "This is a docstring with single quotes."


def test_extract_parameters_no_params():
    source = """def hello():
    pass
"""
    parser = PythonParser()
    tree = parser.parser.parse(bytes(source, "utf8"))
    func_node = tree.root_node.children[0]

    params = parser._extract_parameters(func_node, source)

    assert params == []


def test_extract_parameters_simple():
    source = """def foo(x, y, z):
    pass
"""
    parser = PythonParser()
    tree = parser.parser.parse(bytes(source, "utf8"))
    func_node = tree.root_node.children[0]

    params = parser._extract_parameters(func_node, source)

    assert len(params) == 3
    assert params[0].name == "x"
    assert params[0].type is None
    assert params[0].default is None
    assert params[1].name == "y"
    assert params[2].name == "z"


def test_extract_parameters_with_types():
    source = """def foo(x: int, y: str, z: bool):
    pass
"""
    parser = PythonParser()
    tree = parser.parser.parse(bytes(source, "utf8"))
    func_node = tree.root_node.children[0]

    params = parser._extract_parameters(func_node, source)

    assert len(params) == 3
    assert params[0].name == "x"
    assert params[0].type == "int"
    assert params[0].default is None
    assert params[1].name == "y"
    assert params[1].type == "str"
    assert params[2].name == "z"
    assert params[2].type == "bool"


def test_extract_parameters_with_defaults():
    source = """def foo(x=5, y="hello", z=None):
    pass
"""
    parser = PythonParser()
    tree = parser.parser.parse(bytes(source, "utf8"))
    func_node = tree.root_node.children[0]

    params = parser._extract_parameters(func_node, source)

    assert len(params) == 3
    assert params[0].name == "x"
    assert params[0].type is None
    assert params[0].default == "5"
    assert params[1].name == "y"
    assert params[1].default == '"hello"'
    assert params[2].name == "z"
    assert params[2].default == "None"


def test_extract_parameters_with_types_and_defaults():
    source = """def foo(a, b: int, c=5, d: str = "hello"):
    pass
"""
    parser = PythonParser()
    tree = parser.parser.parse(bytes(source, "utf8"))
    func_node = tree.root_node.children[0]

    params = parser._extract_parameters(func_node, source)

    assert len(params) == 4
    assert params[0].name == "a"
    assert params[0].type is None
    assert params[0].default is None
    assert params[1].name == "b"
    assert params[1].type == "int"
    assert params[1].default is None
    assert params[2].name == "c"
    assert params[2].type is None
    assert params[2].default == "5"
    assert params[3].name == "d"
    assert params[3].type == "str"
    assert params[3].default == '"hello"'


def test_extract_parameters_complex_types():
    source = """def foo(x: list[int], y: dict[str, Any], z: Optional[int] = None):
    pass
"""
    parser = PythonParser()
    tree = parser.parser.parse(bytes(source, "utf8"))
    func_node = tree.root_node.children[0]

    params = parser._extract_parameters(func_node, source)

    assert len(params) == 3
    assert params[0].name == "x"
    assert params[0].type == "list[int]"
    assert params[1].name == "y"
    assert params[1].type == "dict[str, Any]"
    assert params[2].name == "z"
    assert params[2].type == "Optional[int]"
    assert params[2].default == "None"


def test_extract_parameters_with_self():
    source = """def method(self, x: int):
    pass
"""
    parser = PythonParser()
    tree = parser.parser.parse(bytes(source, "utf8"))
    func_node = tree.root_node.children[0]

    params = parser._extract_parameters(func_node, source)

    # We include self for now - it's up to the caller to filter it
    assert len(params) == 2
    assert params[0].name == "self"
    assert params[1].name == "x"


def test_extract_parameters_with_args_kwargs():
    source = """def foo(x, *args, **kwargs):
    pass
"""
    parser = PythonParser()
    tree = parser.parser.parse(bytes(source, "utf8"))
    func_node = tree.root_node.children[0]

    params = parser._extract_parameters(func_node, source)

    assert len(params) == 3
    assert params[0].name == "x"
    assert params[1].name == "*args"
    assert params[2].name == "**kwargs"


def test_extract_return_type():
    source = """def foo() -> bool:
    pass
"""
    parser = PythonParser()
    tree = parser.parser.parse(bytes(source, "utf8"))
    func_node = tree.root_node.children[0]

    return_type = parser._extract_return_type(func_node, source)

    assert return_type == "bool"


def test_extract_return_type_not_present():
    source = """def foo():
    pass
"""
    parser = PythonParser()
    tree = parser.parser.parse(bytes(source, "utf8"))
    func_node = tree.root_node.children[0]

    return_type = parser._extract_return_type(func_node, source)

    assert return_type is None


def test_extract_complex_return_type():
    source = """def foo() -> Optional[dict[str, Any]]:
    pass
"""
    parser = PythonParser()
    tree = parser.parser.parse(bytes(source, "utf8"))
    func_node = tree.root_node.children[0]

    return_type = parser._extract_return_type(func_node, source)

    assert return_type == "Optional[dict[str, Any]]"


def test_extract_return_type_with_params():
    source = """def foo(x: int, y: str = "hello") -> list[int]:
    pass
"""
    parser = PythonParser()
    tree = parser.parser.parse(bytes(source, "utf8"))
    func_node = tree.root_node.children[0]

    return_type = parser._extract_return_type(func_node, source)

    assert return_type == "list[int]"


def test_extract_entity_info_function_with_full_signature():
    source = '''def validateSession(token: str = "abc123") -> bool:
    """Validates JWT token and returns user object."""
    return True
'''
    parser = PythonParser()

    info = parser.extract_entity_info(source, "test.py", "validateSession")

    assert info is not None
    assert info.path == "test.py"
    assert info.extent.start == 0
    assert info.extent.end == 2
    assert info.sig is not None
    assert info.sig.name == "validateSession"
    assert len(info.sig.args) == 1
    assert info.sig.args[0].name == "token"
    assert info.sig.args[0].type == "str"
    assert info.sig.args[0].default == '"abc123"'
    assert info.sig.return_type == "bool"
    assert info.summary == "Validates JWT token and returns user object."


def test_extract_entity_info_function_without_docstring():
    source = """def hello():
    pass
"""
    parser = PythonParser()

    info = parser.extract_entity_info(source, "test.py", "hello")

    assert info is not None
    assert info.sig is not None
    assert info.sig.name == "hello"
    assert info.sig.args == []
    assert info.summary is None


def test_extract_entity_info_method():
    source = '''class MyClass:
    def method(self, x: int) -> str:
        """A method."""
        return str(x)
'''
    parser = PythonParser()

    info = parser.extract_entity_info(source, "test.py", "method")

    assert info is not None
    assert info.sig is not None
    assert info.sig.name == "method"
    assert len(info.sig.args) == 2
    assert info.sig.args[0].name == "self"
    assert info.sig.args[1].name == "x"
    assert info.sig.args[1].type == "int"
    assert info.sig.return_type == "str"
    assert info.summary == "A method."


def test_extract_entity_info_class():
    source = '''class MyClass:
    """This is a class docstring."""
    def method_one(self, x: int) -> str:
        pass

    def method_two(self):
        pass
'''
    parser = PythonParser()

    info = parser.extract_entity_info(source, "test.py", "MyClass")

    assert info is not None
    assert isinstance(info, ClassInfo)
    assert info.path == "test.py"
    assert info.methods == ["method_one(self, x: int) -> str", "method_two(self)"]
    assert info.summary == "This is a class docstring."


def test_extract_entity_info_class_without_docstring():
    source = """class EmptyClass:
    pass
"""
    parser = PythonParser()

    info = parser.extract_entity_info(source, "test.py", "EmptyClass")

    assert info is not None
    assert isinstance(info, ClassInfo)
    assert info.methods == []
    assert info.summary is None


def test_extract_entity_info_module_level():
    source = '''"""This is a module-level docstring."""

def some_function():
    pass
'''
    parser = PythonParser()

    info = parser.extract_entity_info(source, "test.py", None)

    assert info is not None
    assert isinstance(info, ModuleInfo)
    assert info.path == "test.py"
    assert info.extent.start == 0
    assert info.extent.end == 3
    assert info.summary == "This is a module-level docstring."


def test_extract_entity_info_module_without_docstring():
    source = """def some_function():
    pass
"""
    parser = PythonParser()

    info = parser.extract_entity_info(source, "test.py", None)

    assert info is not None
    assert isinstance(info, ModuleInfo)
    assert info.summary is None


def test_extract_entity_info_not_found():
    source = """def hello():
    pass
"""
    parser = PythonParser()

    info = parser.extract_entity_info(source, "test.py", "nonexistent")

    assert info is None


def test_format_signature_with_all_param_types():
    parser = PythonParser()
    params = [
        Parameter(name="a", type="int", default="5"),
        Parameter(name="b", type="str"),
        Parameter(name="c", default="None"),
        Parameter(name="d")
    ]

    sig = parser._format_signature("func", params, "bool")

    assert sig == "func(a: int = 5, b: str, c = None, d) -> bool"


def test_format_signature_no_params():
    parser = PythonParser()

    sig = parser._format_signature("hello", [], None)

    assert sig == "hello()"


def test_format_signature_no_return_type():
    parser = PythonParser()
    params = [Parameter(name="x", type="int")]

    sig = parser._format_signature("func", params, None)

    assert sig == "func(x: int)"


def test_format_signature_complex_types():
    parser = PythonParser()
    params = [
        Parameter(name="x", type="dict[str, Any]"),
        Parameter(name="y", type="Optional[int]", default="None")
    ]

    sig = parser._format_signature("process", params, "list[str]")

    assert sig == "process(x: dict[str, Any], y: Optional[int] = None) -> list[str]"


def test_format_signature_with_args_kwargs():
    parser = PythonParser()
    params = [
        Parameter(name="self"),
        Parameter(name="x", type="int"),
        Parameter(name="*args"),
        Parameter(name="**kwargs")
    ]

    sig = parser._format_signature("method", params, "None")

    assert sig == "method(self, x: int, *args, **kwargs) -> None"
