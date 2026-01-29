import json
import pytest
from src.report import DebugReporter, MarkdownReporter, SarifReporter


@pytest.fixture
def sample_results():
    return {
        "/path/to/src/vuln.py": {
            "structure": {
                "blocks": [
                    {
                        "id": 1,
                        "scope": "function",
                        "security_findings": [
                            {
                                "check_id": "python.lang.security.audit.exec-detected",
                                "line": 10,
                                "column": 5,
                                "message": "Exec detected",
                            }
                        ],
                        "llm_insights": [
                            {
                                "snippet": "exec(user_input)",
                                "analysis": [
                                    {
                                        "check_id": "python.lang.security.audit.exec-detected",
                                        "verdict": "True Positive",
                                        "rationale": "Direct execution of user input.",
                                        "remediation": "Don't use exec.",
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }
        }
    }


def test_markdown_reporter(sample_results, tmp_path):
    reporter = MarkdownReporter()
    output_path = tmp_path / "report.md"
    reporter.generate(sample_results, str(output_path))

    content = output_path.read_text(encoding="utf-8")
    assert "# Neuro-Symbolic Security Scan Report" in content
    assert "File: `/path/to/src/vuln.py`" in content
    assert "exec-detected" in content
    assert "True Positive" in content
    assert "exec(user_input)" in content


def test_sarif_reporter(sample_results, tmp_path):
    reporter = SarifReporter()
    output_path = tmp_path / "report.sarif"
    reporter.generate(sample_results, str(output_path))

    with open(output_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["version"] == "2.1.0"
    assert len(data["runs"]) == 1
    results = data["runs"][0]["results"]
    assert len(results) == 1
    assert results[0]["ruleId"] == "python.lang.security.audit.exec-detected"
    assert results[0]["level"] == "error"  # True Positive -> error

    # Check location
    loc = results[0]["locations"][0]["physicalLocation"]
    assert loc["artifactLocation"]["uri"] == "/path/to/src/vuln.py"
    assert loc["region"]["startLine"] == 10


def test_sarif_reporter_includes_fixes(tmp_path):
    results = {
        "/path/to/src/vuln.py": {
            "structure": {
                "blocks": [
                    {
                        "id": 1,
                        "scope": "function",
                        "security_findings": [
                            {
                                "check_id": "python.lang.security.audit.exec-detected",
                                "line": 10,
                                "column": 5,
                                "message": "Exec detected",
                            }
                        ],
                        "llm_insights": [
                            {
                                "snippet": "exec(user_input)",
                                "analysis": [
                                    {
                                        "check_id": "python.lang.security.audit.exec-detected",
                                        "verdict": "True Positive",
                                        "rationale": "Direct execution of user input.",
                                        "fix_suggestion": "Use a safe wrapper.",
                                        "secure_code_snippet": "safe_code()",
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }
        }
    }

    reporter = SarifReporter()
    output_path = tmp_path / "report.sarif"
    reporter.generate(results, str(output_path))

    with open(output_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    result = data["runs"][0]["results"][0]
    fixes = result["fixes"]
    assert fixes[0]["description"]["text"] == "Use a safe wrapper."

    replacement = fixes[0]["artifactChanges"][0]["replacements"][0]
    assert replacement["insertedContent"]["text"] == "safe_code()"
    assert replacement["deletedRegion"]["startLine"] == 10
    assert replacement["deletedRegion"]["startColumn"] == 5
    assert replacement["deletedRegion"]["endLine"] == 10
    assert replacement["deletedRegion"]["endColumn"] == 16


def test_debug_reporter(tmp_path, sample_results):
    reporter = DebugReporter()
    output_path = tmp_path / "nsss_debug.json"
    reporter.generate(sample_results, str(output_path), metadata={"run_id": "123"})

    with open(output_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    assert payload["metadata"]["run_id"] == "123"
    assert payload["results"] == sample_results
