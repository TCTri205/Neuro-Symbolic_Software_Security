from src.librarian.models import (
    Library,
    LibraryVersion,
    FunctionSpec,
    SecurityLabel,
    ParameterSpec,
)


def test_security_label_enum():
    assert SecurityLabel.SOURCE.value == "source"
    assert SecurityLabel.SINK.value == "sink"
    assert SecurityLabel.SANITIZER.value == "sanitizer"
    assert SecurityLabel.NONE.value == "none"


def test_parameter_spec_creation():
    # Test valid creation
    param = ParameterSpec(name="query", index=0, tags=["sql_injection"])
    assert param.name == "query"
    assert param.index == 0
    assert "sql_injection" in param.tags


def test_function_spec_creation():
    param = ParameterSpec(name="cmd", index=0)
    func = FunctionSpec(
        name="os.system",
        label=SecurityLabel.SINK,
        parameters=[param],
        description="Execute system command",
    )
    assert func.name == "os.system"
    assert func.label == SecurityLabel.SINK
    assert len(func.parameters) == 1


def test_library_version_creation():
    func = FunctionSpec(name="execute", label=SecurityLabel.SINK)
    lib_ver = LibraryVersion(version="1.0.0", functions=[func])
    assert lib_ver.version == "1.0.0"
    assert len(lib_ver.functions) == 1


def test_library_creation():
    func = FunctionSpec(name="execute", label=SecurityLabel.SINK)
    lib_ver = LibraryVersion(version="1.0.0", functions=[func])

    lib = Library(name="test-lib", ecosystem="pypi", versions=[lib_ver])
    assert lib.name == "test-lib"
    assert lib.ecosystem == "pypi"
    assert len(lib.versions) == 1


def test_serialization():
    lib = Library(name="demo", ecosystem="npm", versions=[])
    json_str = lib.model_dump_json()
    assert "demo" in json_str
    assert "npm" in json_str
