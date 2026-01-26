"""
Tests for Embedded Language Detection

Validates detection of SQL, Shell, HTML, JSON, YAML, and RegEx in string literals.
"""

import pytest

from src.core.parser.embedded_lang_detector import (
    EmbeddedLanguageDetector,
    detect_embedded_language,
)


class TestSQLDetection:
    """Test SQL detection with various patterns."""

    def test_select_statement(self):
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect("SELECT * FROM users WHERE id = 1")
        assert lang == "sql"
        assert confidence >= 0.9

    def test_insert_statement(self):
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect(
            "INSERT INTO users (name, email) VALUES ('John', 'john@example.com')"
        )
        assert lang == "sql"
        assert confidence >= 0.9

    def test_update_statement(self):
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect(
            "UPDATE users SET status = 'active' WHERE id = 1"
        )
        assert lang == "sql"
        assert confidence >= 0.9

    def test_create_table(self):
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)"
        )
        assert lang == "sql"
        assert confidence >= 0.9

    def test_complex_query_with_joins(self):
        detector = EmbeddedLanguageDetector()
        sql = """
            SELECT u.name, o.total 
            FROM users u 
            INNER JOIN orders o ON u.id = o.user_id 
            WHERE o.total > 100
        """
        lang, confidence = detector.detect(sql)
        assert lang == "sql"
        assert confidence >= 0.85

    def test_sql_injection_pattern(self):
        # Common SQL injection pattern (from benchmarks/vulnerable_flask_app)
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect(
            "SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"
        )
        assert lang == "sql"
        assert confidence >= 0.9

    def test_not_sql_similar_words(self):
        # Words that might appear in SQL but aren't SQL code
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect("Please select from the menu")
        assert lang is None or confidence < 0.5


class TestShellDetection:
    """Test shell command detection."""

    def test_simple_command_with_flag(self):
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect("ls -la /home/user")
        assert lang == "shell"
        assert confidence >= 0.8

    def test_pipe_operator(self):
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect("cat file.txt | grep 'pattern'")
        assert lang == "shell"
        assert confidence >= 0.85

    def test_redirect_operators(self):
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect("echo 'data' > output.txt")
        assert lang == "shell"
        assert confidence >= 0.8

    def test_command_substitution(self):
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect("echo $(date)")
        assert lang == "shell"
        assert confidence >= 0.9

    def test_chained_commands(self):
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect(
            "mkdir -p /tmp/test && cd /tmp/test && touch file.txt"
        )
        assert lang == "shell"
        assert confidence >= 0.85

    def test_curl_command(self):
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect("curl -X POST https://api.example.com/data")
        assert lang == "shell"
        assert confidence >= 0.9


class TestHTMLDetection:
    """Test HTML/XML detection."""

    def test_simple_html_tag(self):
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect("<div>Hello World</div>")
        assert lang == "html"
        assert confidence >= 0.85

    def test_nested_html(self):
        detector = EmbeddedLanguageDetector()
        html = """
            <html>
                <head><title>Test</title></head>
                <body>
                    <div class="container">
                        <p>Hello World</p>
                    </div>
                </body>
            </html>
        """
        lang, confidence = detector.detect(html)
        assert lang == "html"
        assert confidence >= 0.9

    def test_self_closing_tag(self):
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect("<img src='test.png' />")
        assert lang == "html"
        assert confidence >= 0.85

    def test_doctype(self):
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect("<!DOCTYPE html><html><body></body></html>")
        assert lang == "html"
        assert confidence >= 0.9

    def test_xml_prolog(self):
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect(
            "<?xml version='1.0' encoding='UTF-8'?><root></root>"
        )
        assert lang == "xml"
        assert confidence >= 0.9


class TestJSONDetection:
    """Test JSON detection."""

    def test_simple_json_object(self):
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect('{"name": "John", "age": 30}')
        assert lang == "json"
        assert confidence >= 0.9

    def test_json_array(self):
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect("[1, 2, 3, 4, 5]")
        assert lang == "json"
        assert confidence >= 0.9

    def test_nested_json(self):
        detector = EmbeddedLanguageDetector()
        json_str = """
        {
            "user": {
                "name": "John Doe",
                "email": "john@example.com",
                "roles": ["admin", "user"]
            }
        }
        """
        lang, confidence = detector.detect(json_str)
        assert lang == "json"
        assert confidence >= 0.9

    def test_invalid_json_not_detected(self):
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect('{"name": "John", invalid}')
        # Should either not detect or have low confidence
        assert lang is None or confidence < 0.7


class TestYAMLDetection:
    """Test YAML detection."""

    def test_simple_yaml(self):
        detector = EmbeddedLanguageDetector()
        yaml_str = """
        name: John Doe
        age: 30
        city: New York
        """
        lang, confidence = detector.detect(yaml_str)
        assert lang == "yaml"
        assert confidence >= 0.7

    def test_yaml_list(self):
        detector = EmbeddedLanguageDetector()
        yaml_str = """
        - item1
        - item2
        - item3
        """
        lang, confidence = detector.detect(yaml_str)
        # Could be detected as YAML or might be ambiguous
        assert lang == "yaml" or confidence < 0.7

    def test_complex_yaml(self):
        detector = EmbeddedLanguageDetector()
        yaml_str = """
        database:
          host: localhost
          port: 5432
          credentials:
            username: admin
            password: secret
        """
        lang, confidence = detector.detect(yaml_str)
        assert lang == "yaml"
        assert confidence >= 0.8


class TestRegexDetection:
    """Test regular expression detection."""

    def test_simple_regex_pattern(self):
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect(r"\d{3}-\d{3}-\d{4}")
        assert lang == "regex"
        assert confidence >= 0.7

    def test_email_regex(self):
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect(
            r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        )
        assert lang == "regex"
        assert confidence >= 0.8

    def test_complex_regex_with_groups(self):
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect(
            r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})Z$"
        )
        assert lang == "regex"
        assert confidence >= 0.8

    def test_character_classes(self):
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect(r"[A-Za-z0-9_]+")
        assert lang == "regex"
        assert confidence >= 0.7


class TestEdgeCases:
    """Test edge cases and ambiguous inputs."""

    def test_empty_string(self):
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect("")
        assert lang is None
        assert confidence == 0.0

    def test_very_short_string(self):
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect("hi")
        assert lang is None
        assert confidence == 0.0

    def test_none_input(self):
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect(None)
        assert lang is None
        assert confidence == 0.0

    def test_non_string_input(self):
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect(123)
        assert lang is None
        assert confidence == 0.0

    def test_plain_text(self):
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect("This is just a regular sentence.")
        assert lang is None or confidence < 0.5

    def test_url_not_detected(self):
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect("https://example.com/api/users")
        # URL might trigger some patterns, but confidence should be low
        assert lang is None or confidence < 0.7


class TestPriorityOrdering:
    """Test that detection prioritizes correctly when multiple languages match."""

    def test_sql_over_shell(self):
        # SQL should take priority for security-critical patterns
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect("SELECT * FROM users")
        assert lang == "sql"

    def test_html_over_regex(self):
        # HTML tags should be detected as HTML, not regex
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect("<div class='test'>Content</div>")
        assert lang == "html"

    def test_json_over_yaml(self):
        # Valid JSON should be detected as JSON
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect('{"key": "value"}')
        assert lang == "json"


class TestConvenienceFunction:
    """Test the global convenience function."""

    def test_detect_embedded_language_function(self):
        lang, confidence = detect_embedded_language("SELECT * FROM users")
        assert lang == "sql"
        assert confidence >= 0.9

    def test_convenience_function_returns_tuple(self):
        result = detect_embedded_language("echo 'hello'")
        assert isinstance(result, tuple)
        assert len(result) == 2
        lang, confidence = result
        assert isinstance(lang, (str, type(None)))
        assert isinstance(confidence, float)


class TestRealWorldExamples:
    """Test with real-world examples from the codebase."""

    def test_sqlite_query_from_librarian(self):
        # From src/librarian/db.py
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect(
            "SELECT * FROM library_profiles WHERE library_name = ?"
        )
        assert lang == "sql"
        assert confidence >= 0.9

    def test_create_table_from_librarian(self):
        # From src/librarian/db.py
        detector = EmbeddedLanguageDetector()
        sql = """
            CREATE TABLE IF NOT EXISTS decisions (
                hash TEXT PRIMARY KEY,
                check_id TEXT,
                verdict TEXT
            )
        """
        lang, confidence = detector.detect(sql)
        assert lang == "sql"
        assert confidence >= 0.9

    def test_vulnerable_sql_from_benchmark(self):
        # From benchmarks/vulnerable_flask_app/app.py
        detector = EmbeddedLanguageDetector()
        lang, confidence = detector.detect(
            "SELECT * FROM users WHERE username = '{username}' AND password = '{hashed_password}'"
        )
        assert lang == "sql"
        assert confidence >= 0.9
