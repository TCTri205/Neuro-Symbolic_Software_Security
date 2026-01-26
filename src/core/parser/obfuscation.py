import math
import os
import re
from typing import List, Tuple


BINARY_EXTENSIONS = {".so", ".pyd", ".dll", ".dylib", ".pyc"}

_MIN_SOURCE_LEN = 200
_LONG_LINE_LEN = 300
_LONG_LINE_RATIO = 0.2
_AVG_LINE_LEN = 120
_NON_PRINTABLE_RATIO = 0.02
_SYMBOL_RATIO = 0.45
_LONG_IDENTIFIER_LEN = 30
_LONG_IDENTIFIER_MIN_COUNT = 10
_LONG_IDENTIFIER_RATIO = 0.25
_ENTROPY_THRESHOLD = 4.8


def is_binary_extension(file_path: str) -> bool:
    _, ext = os.path.splitext(file_path)
    return ext.lower() in BINARY_EXTENSIONS


def detect_obfuscation(source: str) -> Tuple[bool, List[str]]:
    if not source:
        return False, []

    if "\x00" in source:
        return True, ["null_byte"]

    if len(source) < _MIN_SOURCE_LEN:
        return False, []

    reasons: List[str] = []
    total = len(source)
    non_printable = sum(1 for ch in source if not _is_printable(ch))
    if total and (non_printable / total) > _NON_PRINTABLE_RATIO:
        reasons.append("non_printable_ratio")

    lines = source.splitlines() or [source]
    long_lines = sum(1 for line in lines if len(line) >= _LONG_LINE_LEN)
    avg_line_len = sum(len(line) for line in lines) / len(lines)
    if (
        lines
        and (long_lines / len(lines)) > _LONG_LINE_RATIO
        and avg_line_len > _AVG_LINE_LEN
    ):
        reasons.append("long_lines")

    symbol_chars = sum(1 for ch in source if not ch.isalnum() and not ch.isspace())
    if total and (symbol_chars / total) > _SYMBOL_RATIO:
        reasons.append("symbol_density")

    identifiers = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", source)
    long_identifiers = [
        name for name in identifiers if len(name) >= _LONG_IDENTIFIER_LEN
    ]
    if (
        identifiers
        and len(long_identifiers) >= _LONG_IDENTIFIER_MIN_COUNT
        and (len(long_identifiers) / len(identifiers)) > _LONG_IDENTIFIER_RATIO
    ):
        reasons.append("long_identifiers")

    entropy = _shannon_entropy(source[:2000])
    if entropy > _ENTROPY_THRESHOLD:
        reasons.append("high_entropy")

    return len(reasons) >= 2, reasons


def _is_printable(ch: str) -> bool:
    return ch.isprintable() or ch in {"\n", "\r", "\t"}


def _shannon_entropy(data: str) -> float:
    if not data:
        return 0.0
    length = len(data)
    counts = {}
    for ch in data:
        counts[ch] = counts.get(ch, 0) + 1
    entropy = 0.0
    for count in counts.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy
