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
