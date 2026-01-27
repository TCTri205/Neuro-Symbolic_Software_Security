import ast
from src.core.cfg.builder import CFGBuilder
from src.core.cfg.signature import SignatureExtractor


def test_signature_extraction_basic():
    code = """
def my_func(a: int, b: str) -> bool:
    print(b)
    if a > 0:
        return True
    return False
    """
    node = ast.parse(code)
    builder = CFGBuilder()
    cfg = builder.build("test_module", node)

    extractor = SignatureExtractor(cfg)
    signatures = extractor.extract()

    assert len(signatures) == 1
    sig = signatures[0]
    assert sig.name == "my_func"
    assert len(sig.inputs) == 2
    assert sig.inputs[0]["name"] == "a"
    assert sig.inputs[0]["type"] == "int"
    assert sig.inputs[1]["name"] == "b"
    assert sig.inputs[1]["type"] == "str"
    assert sig.outputs == ["bool"]
    assert "print" in sig.calls
    assert sig.complexity >= 2  # 1 base + 1 if


def test_signature_extraction_complex():
    code = """
import os

def process_data(data: list) -> None:
    for item in data:
        if item:
            os.path.join("a", "b")
        else:
            log("error")
    """
    node = ast.parse(code)
    builder = CFGBuilder()
    cfg = builder.build("test_complex", node)

    extractor = SignatureExtractor(cfg)
    signatures = extractor.extract()

    assert len(signatures) == 1
    sig = signatures[0]
    assert sig.name == "process_data"
    assert "os.path.join" in sig.calls
    assert "log" in sig.calls
    # Complexity: Base (1) + For (1 loop) + If (1 branch) = 3?
    # Logic in extractor:
    # For loop has header (split to body/exit) -> out degree 2 -> +1
    # If has pred (split to then/else) -> out degree 2 -> +1
    # So complexity should be 1 + 1 + 1 = 3.
    assert sig.complexity >= 3


def test_signature_side_effects():
    import textwrap

    code = textwrap.dedent("""
    x = 0
    def modify_global():
        global x
        x = 1
        print("Modified x")

    def network_call():
        import requests
        requests.get("http://example.com")
    """)
    node = ast.parse(code)

    builder = CFGBuilder()
    cfg = builder.build("test_side_effects", node)

    extractor = SignatureExtractor(cfg)
    signatures = extractor.extract()

    # Find modify_global
    sig_global = next(s for s in signatures if s.name == "modify_global")
    # We expect global write detection
    assert any("global:write:x" in se for se in sig_global.side_effects)
    # We expect io detection
    assert any("io:print" in se for se in sig_global.side_effects)

    # Find network_call
    sig_net = next(s for s in signatures if s.name == "network_call")
    # We expect network detection (heuristic)
    assert any("net:requests.get" in se for se in sig_net.side_effects)


def test_signature_taint_fields_exist():
    code = """
def sensitive_func(password: str):
    pass
    """
    node = ast.parse(code)
    builder = CFGBuilder()
    cfg = builder.build("test_taint", node)

    extractor = SignatureExtractor(cfg)
    signatures = extractor.extract()
    sig = signatures[0]

    # Verify fields exist (even if empty for now, unless we implement heuristics)
    assert hasattr(sig, "taint_sources")
    assert hasattr(sig, "taint_sinks")
    assert isinstance(sig.taint_sources, list)
    assert isinstance(sig.taint_sinks, list)
