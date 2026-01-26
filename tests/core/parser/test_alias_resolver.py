from src.core.parser.alias_resolver import resolve_aliased_calls
from src.core.parser.python_ast import PythonAstParser


def _calls_with_resolved(graph, resolved):
    return [
        node
        for node in graph.nodes
        if node.kind == "Call" and node.attrs.get("resolved_callee") == resolved
    ]


def test_alias_resolver_marks_assigned_alias() -> None:
    source = """
import os as o

def run(cmd):
    system_call = o.system
    return system_call(cmd)
"""
    parser = PythonAstParser(
        source,
        "alias.py",
        enable_alias_resolution=False,
        enable_dynamic_tagging=False,
    )
    graph = parser.parse()
    resolve_aliased_calls(graph)

    calls = _calls_with_resolved(graph, "os.system")
    assert calls
    assert "sink" in calls[0].attrs.get("tags", [])
    assert "alias" in calls[0].attrs.get("tags", [])


def test_alias_resolver_marks_from_import_alias() -> None:
    source = """
from subprocess import run as runner

def run(cmd):
    return runner(cmd)
"""
    parser = PythonAstParser(
        source,
        "alias.py",
        enable_alias_resolution=False,
        enable_dynamic_tagging=False,
    )
    graph = parser.parse()
    resolve_aliased_calls(graph)

    calls = _calls_with_resolved(graph, "subprocess.run")
    assert calls
    assert "sink" in calls[0].attrs.get("tags", [])
    assert "alias" in calls[0].attrs.get("tags", [])


def test_alias_resolver_marks_module_alias_attribute() -> None:
    source = """
import subprocess as sp

def run(cmd):
    return sp.Popen(cmd)
"""
    parser = PythonAstParser(
        source,
        "alias.py",
        enable_alias_resolution=False,
        enable_dynamic_tagging=False,
    )
    graph = parser.parse()
    resolve_aliased_calls(graph)

    calls = _calls_with_resolved(graph, "subprocess.Popen")
    assert calls
    assert "sink" in calls[0].attrs.get("tags", [])
    assert "alias" in calls[0].attrs.get("tags", [])
