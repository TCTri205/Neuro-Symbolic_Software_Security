import json
from unittest.mock import MagicMock, patch
import pytest
from src.core.pipeline.orchestrator import AnalysisOrchestrator
from src.report.sarif import SarifReporter
from src.core.ai.client import LLMClient


@pytest.fixture
def mock_llm_client():
    client = MagicMock(spec=LLMClient)
    client.provider = "mock"
    client.model = "test-model"
    client.is_configured = True
    return client


def test_autofix_workflow_e2e(tmp_path, mock_llm_client):
    """
    Test the full autofix flow:
    1. Static analysis finds a vulnerability (we'll mock Semgrep or use a simple pattern).
    2. LLM is invoked and returns a fix.
    3. Orchestrator captures the fix.
    4. SARIF reporter outputs the fix.
    """

    # 1. Setup
    # We need a vulnerability that triggers the LLM.
    # The orchestrator runs semgrep. We can mock semgrep results.

    source_code = """
def vulnerable_function(uid):
    query = f"SELECT * FROM users WHERE id = {uid}"
    execute(query)
"""
    file_path = "src/vuln.py"

    # Mock Semgrep output
    semgrep_results = {
        "results": [
            {
                "check_id": "python.lang.security.audit.formatted-sql-query",
                "path": file_path,
                "start": {"line": 3, "col": 5},
                "extra": {"message": "Potential SQL Injection", "severity": "ERROR"},
            }
        ]
    }

    # Mock LLM Response with Fix
    fix_content = {
        "analysis": [
            {
                "check_id": "python.lang.security.audit.formatted-sql-query",
                "verdict": "True Positive",
                "rationale": "User input is directly concatenated into SQL query.",
                "remediation": "Use parameterized queries.",
                "fix_suggestion": "Replace f-string with parameterized query.",
                "secure_code_snippet": 'query = "SELECT * FROM users WHERE id = %s"\n    execute(query, (uid,))',
                "confidence_score": 0.95,
                "risk_level": "HIGH",
                "reasoning_trace": "Data flows from uid to query...",
                "analysis_summary": "Confirmed SQL Injection.",
            }
        ]
    }

    mock_llm_client.chat.return_value = {
        "content": json.dumps(fix_content),
        "status": "success",
    }

    # 2. Run Orchestrator
    # We patch LLMClient to return our mock
    with patch(
        "src.core.pipeline.orchestrator.LLMClient", return_value=mock_llm_client
    ):
        # We also need to patch SemgrepRunner to return our findings
        with patch("src.core.pipeline.orchestrator.SemgrepRunner") as MockSemgrep:
            MockSemgrep.return_value.run.return_value = semgrep_results

            orchestrator = AnalysisOrchestrator(enable_ir=False)
            # Force enable gatekeeper for "mock" provider if needed, or just rely on defaults
            # The orchestrator calls gatekeeper.preferred_provider() -> likely "openai" or similar.
            # We need to ensure LLMClient is instantiated with that provider and matches our mock.
            # The patch above patches the class, so any instantiation returns mock_llm_client.

            result = orchestrator.analyze_code(source_code, file_path)

    # 3. Verify Insights
    assert len(result.cfg._blocks) > 0
    found_insight = False
    for block in result.cfg._blocks.values():
        if block.llm_insights:
            for insight in block.llm_insights:
                for analysis in insight.get("analysis", []):
                    if (
                        analysis.get("check_id")
                        == "python.lang.security.audit.formatted-sql-query"
                    ):
                        found_insight = True
                        assert (
                            analysis["fix_suggestion"]
                            == "Replace f-string with parameterized query."
                        )
                        assert "secure_code_snippet" in analysis
                        assert (
                            "execute(query, (uid,))" in analysis["secure_code_snippet"]
                        )

    assert found_insight, "LLM insight with fix not found in CFG blocks"

    # 4. Generate SARIF
    reporter = SarifReporter()
    output_path = tmp_path / "report.sarif"
    reporter.generate({file_path: result.to_dict()}, str(output_path))

    # 5. Verify SARIF Content
    with open(output_path, "r") as f:
        sarif_data = json.load(f)

    run = sarif_data["runs"][0]
    results = run["results"]
    assert len(results) == 1

    res = results[0]
    assert "fixes" in res
    fix = res["fixes"][0]
    assert fix["description"]["text"] == "Replace f-string with parameterized query."

    changes = fix["artifactChanges"][0]
    replacements = changes["replacements"][0]
    inserted = replacements["insertedContent"]["text"]

    assert "execute(query, (uid,))" in inserted
    assert "deletedRegion" in replacements
