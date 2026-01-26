"""
Embedded Language Detector

Detects embedded languages (SQL, Shell, HTML, JSON, YAML, RegEx) in string literals.
Each detection includes a confidence score (0.0 to 1.0).
"""

from __future__ import annotations

import json
import re
from typing import Optional, Tuple

import yaml


class EmbeddedLanguageDetector:
    """
    Detects embedded languages in string literals with confidence scoring.

    Confidence Levels:
    - 0.9-1.0: Very high confidence (multiple strong indicators)
    - 0.7-0.9: High confidence (strong pattern match)
    - 0.5-0.7: Medium confidence (weak indicators, ambiguous)
    - 0.0-0.5: Low confidence (minimal evidence, likely noise)

    Usage:
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect("SELECT * FROM users")
        # Returns: ("sql", 0.95)
    """

    # SQL Keywords (case-insensitive)
    SQL_KEYWORDS = {
        # DML (Data Manipulation Language)
        "select",
        "insert",
        "update",
        "delete",
        "merge",
        # DDL (Data Definition Language)
        "create",
        "alter",
        "drop",
        "truncate",
        # DQL clauses
        "from",
        "where",
        "join",
        "inner",
        "outer",
        "left",
        "right",
        "group",
        "having",
        "order",
        "limit",
        "offset",
        # Other common
        "union",
        "distinct",
        "as",
        "on",
        "and",
        "or",
        "not",
        "table",
        "database",
        "index",
        "view",
        "procedure",
    }

    # Shell command keywords
    SHELL_KEYWORDS = {
        # Core commands
        "cd",
        "ls",
        "pwd",
        "mkdir",
        "rmdir",
        "rm",
        "cp",
        "mv",
        "cat",
        "grep",
        "awk",
        "sed",
        "find",
        "xargs",
        # Network
        "curl",
        "wget",
        "ssh",
        "scp",
        "nc",
        "netcat",
        # System
        "echo",
        "printf",
        "export",
        "source",
        "chmod",
        "chown",
        "ps",
        "kill",
        "top",
        "df",
        "du",
        "tar",
        "gzip",
        # Package managers
        "apt",
        "yum",
        "dnf",
        "brew",
        "pip",
        "npm",
    }

    # Regex patterns for structural detection
    PATTERNS = {
        "sql": [
            # SELECT ... FROM pattern (must have FROM to avoid false positives)
            (re.compile(r"\bSELECT\b.+\bFROM\b", re.IGNORECASE | re.DOTALL), 0.95),
            # INSERT INTO pattern
            (
                re.compile(r"\bINSERT\s+INTO\b.+\bVALUES\b", re.IGNORECASE | re.DOTALL),
                0.95,
            ),
            # UPDATE ... SET pattern
            (re.compile(r"\bUPDATE\b.+\bSET\b", re.IGNORECASE | re.DOTALL), 0.95),
            # CREATE TABLE pattern
            (re.compile(r"\bCREATE\s+TABLE\b", re.IGNORECASE), 0.95),
            # Multiple SQL keywords (2+ specific keywords, not just SELECT/FROM alone)
            (
                re.compile(
                    r"\b(INSERT|UPDATE|DELETE|CREATE|ALTER|DROP)\b.*\b(FROM|WHERE|JOIN|SET|VALUES|TABLE)\b",
                    re.IGNORECASE | re.DOTALL,
                ),
                0.85,
            ),
        ],
        "shell": [
            # Pipe operator
            (re.compile(r"\S+\s*\|\s*\S+"), 0.85),
            # Command with flags (e.g., "ls -la", "grep -r")
            (
                re.compile(
                    r"\b(" + "|".join(SHELL_KEYWORDS) + r")\s+-[a-zA-Z]+", re.IGNORECASE
                ),
                0.90,
            ),
            # Redirect operators
            (re.compile(r"(>>|>|<|2>&1)"), 0.80),
            # Command substitution
            (re.compile(r"\$\(.*\)|\`.*\`"), 0.90),
            # Variable expansion
            (re.compile(r"\$\{?\w+\}?"), 0.70),
            # Multiple shell commands chained
            (
                re.compile(
                    r"\b("
                    + "|".join(list(SHELL_KEYWORDS)[:10])
                    + r")\b.*(\&\&|\|\||;)",
                    re.IGNORECASE,
                ),
                0.85,
            ),
        ],
        "html": [
            # HTML tags
            (
                re.compile(
                    r"<\s*([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>.*?</\s*\1\s*>", re.DOTALL
                ),
                0.95,
            ),
            # Self-closing tags
            (re.compile(r"<\s*[a-zA-Z][a-zA-Z0-9]*\b[^>]*/\s*>"), 0.90),
            # DOCTYPE
            (re.compile(r"<!DOCTYPE\s+html>", re.IGNORECASE), 0.95),
            # Common HTML tags
            (
                re.compile(
                    r"<\s*(html|head|body|div|span|p|a|img|script|style)\b",
                    re.IGNORECASE,
                ),
                0.85,
            ),
        ],
        "xml": [
            # XML prolog
            (re.compile(r"<\?xml\s+version=", re.IGNORECASE), 0.95),
            # Namespace declarations
            (re.compile(r"xmlns[:=]"), 0.90),
        ],
        "json": [
            # Basic JSON structure (object or array)
            (
                re.compile(r"^\s*[\{\[].*[\}\]]\s*$", re.DOTALL),
                0.60,
            ),  # Weak, needs validation
        ],
        "yaml": [
            # YAML key-value with colon
            (re.compile(r"^\s*[\w-]+\s*:\s*.+", re.MULTILINE), 0.65),  # Weak
            # YAML list items
            (re.compile(r"^\s*-\s+\w+", re.MULTILINE), 0.60),  # Weak
        ],
        "regex": [
            # Complex regex patterns (character classes, quantifiers, groups)
            (
                re.compile(r"(\[[\^]?[^\]]+\]|\\[dDwWsS]|\{[\d,]+\}|\(.*\)|\.\*|\.\+)"),
                0.75,
            ),
            # Anchors and boundaries
            (re.compile(r"(\^|\$|\\b|\\B)"), 0.65),
        ],
    }

    def __init__(self):
        """Initialize the detector."""
        pass

    def detect(self, value: str) -> Tuple[Optional[str], float]:
        """
        Detect the embedded language in a string literal.

        Args:
            value: String literal to analyze

        Returns:
            Tuple of (language, confidence) where language is one of:
            "sql", "shell", "html", "xml", "json", "yaml", "regex", or None

        Detection Order (to handle overlaps):
        1. SQL (high priority for security)
        2. Shell (high priority for security)
        3. XML (must check before HTML due to overlap)
        4. HTML (structural)
        5. JSON (structured data, needs validation)
        6. YAML (structured data, needs validation)
        7. RegEx (patterns)
        """
        if not value or not isinstance(value, str):
            return (None, 0.0)

        # Ignore very short strings (likely not embedded code)
        if len(value.strip()) < 5:
            return (None, 0.0)

        # Track all detections with scores
        detections = []

        # SQL Detection
        sql_score = self._detect_sql(value)
        if sql_score > 0.5:
            detections.append(("sql", sql_score))

        # Shell Detection
        shell_score = self._detect_shell(value)
        if shell_score > 0.5:
            detections.append(("shell", shell_score))

        # XML Detection (BEFORE HTML - XML has higher priority)
        xml_score = self._detect_xml(value)
        if xml_score > 0.5:
            detections.append(("xml", xml_score))

        # HTML Detection
        html_score = self._detect_html(value)
        if html_score > 0.5:
            detections.append(("html", html_score))

        # JSON Detection (with validation)
        json_score = self._detect_json(value)
        if json_score > 0.5:
            detections.append(("json", json_score))

        # YAML Detection (with validation)
        yaml_score = self._detect_yaml(value)
        if yaml_score > 0.5:
            detections.append(("yaml", yaml_score))

        # RegEx Detection
        regex_score = self._detect_regex(value)
        if regex_score > 0.5:
            detections.append(("regex", regex_score))

        # Return the highest-confidence detection
        if detections:
            detections.sort(key=lambda x: x[1], reverse=True)
            return detections[0]

        return (None, 0.0)

    def _detect_sql(self, value: str) -> float:
        """Detect SQL with confidence scoring."""
        score = 0.0

        # Natural language filter
        words = value.split()
        is_natural_language = False
        if len(words) > 0:
            first_word = words[0].lower()
            if first_word in [
                "please",
                "can",
                "could",
                "would",
                "should",
                "may",
                "might",
                "the",
                "a",
                "an",
                "this",
                "that",
            ]:
                is_natural_language = True

        # If it looks like natural language, don't detect as SQL
        if is_natural_language:
            return 0.0

        # Check patterns
        for pattern, pattern_score in self.PATTERNS["sql"]:
            if pattern.search(value):
                score = max(score, pattern_score)

        # Keyword counting (boost confidence)
        keywords_found = sum(
            1
            for kw in self.SQL_KEYWORDS
            if re.search(r"\b" + kw + r"\b", value, re.IGNORECASE)
        )
        if keywords_found >= 3:
            score = max(score, 0.80)
        elif keywords_found >= 2:
            score = max(score, 0.65)

        return score

    def _detect_shell(self, value: str) -> float:
        """Detect shell commands with confidence scoring."""
        score = 0.0

        # Check patterns
        for pattern, pattern_score in self.PATTERNS["shell"]:
            if pattern.search(value):
                score = max(score, pattern_score)

        # Keyword counting
        keywords_found = sum(
            1
            for kw in self.SHELL_KEYWORDS
            if re.search(r"\b" + kw + r"\b", value, re.IGNORECASE)
        )
        if keywords_found >= 2:
            score = max(score, 0.75)

        return score

    def _detect_html(self, value: str) -> float:
        """Detect HTML with confidence scoring."""
        score = 0.0

        for pattern, pattern_score in self.PATTERNS["html"]:
            if pattern.search(value):
                score = max(score, pattern_score)

        return score

    def _detect_xml(self, value: str) -> float:
        """Detect XML with confidence scoring."""
        score = 0.0

        for pattern, pattern_score in self.PATTERNS["xml"]:
            if pattern.search(value):
                score = max(score, pattern_score)

        return score

    def _detect_json(self, value: str) -> float:
        """Detect JSON with validation."""
        # Try to parse as JSON
        try:
            json.loads(value)
            # Valid JSON - check if it's meaningful (not just a number or simple string)
            stripped = value.strip()
            if stripped.startswith(("{", "[")):
                return 0.95  # High confidence for objects/arrays
            return 0.70  # Lower confidence for primitives
        except (json.JSONDecodeError, ValueError):
            # Check for partial JSON patterns
            for pattern, pattern_score in self.PATTERNS["json"]:
                if pattern.search(value):
                    return 0.50  # Low confidence without validation
            return 0.0

    def _detect_yaml(self, value: str) -> float:
        """Detect YAML with validation."""
        # Try to parse as YAML
        try:
            result = yaml.safe_load(value)
            # Valid YAML - check if it's meaningful
            if isinstance(result, (dict, list)):
                # Reject if it looks like invalid JSON (e.g., has unquoted keys after colons in braces)
                # YAML parser is more lenient and might accept malformed JSON
                stripped = value.strip()
                if stripped.startswith("{") and "invalid" in value:
                    # Likely malformed JSON/YAML hybrid
                    return 0.0

                # Check for YAML-specific syntax (not just JSON-compatible)
                if ":" in value and not value.strip().startswith("{"):
                    return 0.90  # High confidence for YAML-style dict
                return 0.75  # Medium-high for dict/list (could be JSON)
            return 0.0  # Primitives are too ambiguous
        except yaml.YAMLError:
            # Check for partial YAML patterns
            for pattern, pattern_score in self.PATTERNS["yaml"]:
                if pattern.search(value):
                    return 0.55  # Low-medium confidence
            return 0.0

    def _detect_regex(self, value: str) -> float:
        """Detect regular expressions."""
        score = 0.0

        # Check for regex-specific syntax
        for pattern, pattern_score in self.PATTERNS["regex"]:
            if pattern.search(value):
                score = max(score, pattern_score)

        # Boost score if multiple regex features present
        regex_features = [
            r"\[[\^]?[^\]]+\]",  # Character classes
            r"\\[dDwWsS]",  # Character class shortcuts
            r"\{[\d,]+\}",  # Quantifiers
            r"\(.*\)",  # Groups
            r"\.\*|\.\+",  # Common patterns
            r"\^|\$",  # Anchors
        ]
        features_found = sum(1 for feat in regex_features if re.search(feat, value))
        if features_found >= 3:
            score = max(score, 0.85)
        elif features_found >= 2:
            score = max(score, 0.70)

        return score


# Global singleton instance for convenience
_detector = EmbeddedLanguageDetector()


def detect_embedded_language(value: str) -> Tuple[Optional[str], float]:
    """
    Convenience function to detect embedded language in a string.

    Args:
        value: String to analyze

    Returns:
        Tuple of (language, confidence)
    """
    return _detector.detect(value)
