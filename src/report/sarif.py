import json
from typing import Dict, Any
from .base import BaseReporter


class SarifReporter(BaseReporter):
    def generate(self, results: Dict[str, Any], output_path: str) -> None:
        """
        Generates a SARIF report from the pipeline results.
        """
        sarif_results = []
        rules = {}

        for file_path, file_data in results.items():
            if "error" in file_data:
                continue

            structure = file_data.get("structure", {})
            blocks = structure.get("blocks", [])

            for block in blocks:
                security_findings = block.get("security_findings", [])
                llm_insights = block.get("llm_insights", [])

                # Build a lookup for insights: check_id -> insight_item
                # Note: This assumes one insight per check_id per block, which is reasonable for now.
                insight_map = {}
                for insight in llm_insights:
                    for item in insight.get("analysis", []):
                        cid = item.get("check_id")
                        if cid:
                            insight_map[cid] = item

                for finding in security_findings:
                    check_id = finding.get("check_id")
                    if not check_id:
                        continue

                    # Enrich with insight if available
                    insight_item = insight_map.get(check_id)

                    if insight_item:
                        verdict = insight_item.get("verdict", "needs_review").lower()
                        rationale = insight_item.get("rationale", "")
                        remediation = insight_item.get("remediation", "")
                    else:
                        verdict = "unverified"
                        rationale = finding.get(
                            "message", "Detected by static analysis."
                        )
                        remediation = "LLM analysis skipped."

                    # Determine level based on verdict
                    if "true positive" in verdict:
                        level = "error"
                    elif "false positive" in verdict:
                        level = "note"
                    elif "unverified" in verdict:
                        level = "warning"
                    else:
                        level = "warning"

                    # Register rule if new
                    if check_id not in rules:
                        rules[check_id] = {
                            "id": check_id,
                            "shortDescription": {"text": f"Security check {check_id}"},
                            "helpUri": f"https://semgrep.dev/r/{check_id}"
                            if "semgrep" in str(check_id).lower()
                            else None,
                        }

                    # Construct Location
                    loc = {
                        "physicalLocation": {
                            "artifactLocation": {"uri": file_path.replace("\\", "/")},
                            "region": {
                                "startLine": finding.get("line", 1),
                                "startColumn": finding.get("column", 1),
                            },
                        }
                    }

                    result = {
                        "ruleId": check_id,
                        "level": level,
                        "message": {
                            "text": f"{verdict.title()}: {rationale}\n\nRemediation:\n{remediation}"
                        },
                        "locations": [loc],
                        "properties": {"verdict": verdict, "remediation": remediation},
                    }
                    sarif_results.append(result)

        tool_component = {
            "name": "Neuro-Symbolic Software Security",
            "version": "1.0.0",
            "rules": list(rules.values()),
        }

        sarif_log = {
            "version": "2.1.0",
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "runs": [{"tool": {"driver": tool_component}, "results": sarif_results}],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(sarif_log, f, indent=2)
