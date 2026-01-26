from src.core.parser.obfuscation import detect_obfuscation, is_binary_extension


def test_detect_obfuscation_skips_normal_code() -> None:
    source = "def add(a, b):\n    return a + b\n"
    flagged, reasons = detect_obfuscation(source)
    assert flagged is False
    assert reasons == []


def test_detect_obfuscation_flags_long_entropy_line() -> None:
    payload = "".join(chr(33 + (i % 90)) for i in range(1200))
    source = f"data = '{payload}'\n"
    flagged, reasons = detect_obfuscation(source)
    assert flagged is True
    assert "long_lines" in reasons
    assert "high_entropy" in reasons


def test_is_binary_extension() -> None:
    assert is_binary_extension("module.so")
    assert is_binary_extension("ext.PYD")
    assert not is_binary_extension("script.py")
