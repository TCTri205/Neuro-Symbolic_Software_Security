import json
from typing import Dict, Any, List
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
                
                # Create a map of check_id -> [findings] for easy lookup of location
                findings_map = {}
                for finding in security_findings:
                    cid = finding.get("check_id")
                    if cid:
                        if cid not in findings_map:
                            findings_map[cid] = []
                        findings_map[cid].append(finding)

                # Process insights
                for insight in llm_insights:
                    analysis_list = insight.get("analysis", [])
                    for item in analysis_list:
                        check_id = item.get("check_id")
                        verdict = item.get("verdict", "needs_review").lower()
                        rationale = item.get("rationale", "")
                        remediation = item.get("remediation", "")
                        
                        # Determine level based on verdict
                        if "true positive" in verdict:
                            level = "error"
                        elif "false positive" in verdict:
                            # In SARIF, FPs are often suppressed or marked as 'none'/'note'
                            # We will log them as 'note' but maybe we should exclude them?
                            # Let's keep them as 'note' with specific kind.
                            level = "note"
                        else:
                            level = "warning"

                        # Register rule if new
                        if check_id and check_id not in rules:
                            rules[check_id] = {
                                "id": check_id,
                                "shortDescription": {
                                    "text": f"Security check {check_id}"
                                },
                                "helpUri": f"https://semgrep.dev/r/{check_id}" if "semgrep" in str(check_id).lower() else None
                            }

                        # Find locations
                        related_findings = findings_map.get(check_id, [])
                        
                        # If we have locations, create a result for each (or aggregate?)
                        # Typically one analysis result -> one SARIF result per location.
                        
                        locations = []
                        if related_findings:
                            for f in related_findings:
                                loc = {
                                    "physicalLocation": {
                                        "artifactLocation": {
                                            "uri": file_path.replace("\\", "/") # SARIF prefers forward slashes
                                        },
                                        "region": {
                                            "startLine": f.get("line", 1),
                                            "startColumn": f.get("column", 1)
                                        }
                                    }
                                }
                                locations.append(loc)
                        else:
                            # Fallback if no specific line found but analysis exists for block
                            locations.append({
                                "physicalLocation": {
                                    "artifactLocation": {
                                        "uri": file_path.replace("\\", "/")
                                    },
                                    "region": {
                                        "startLine": 1 # Fallback
                                    }
                                }
                            })

                        # Construct SARIF result
                        # If there are multiple locations for the same check in the same block, 
                        # we can either emit multiple results or one result with multiple locations.
                        # Usually it's better to emit one result per location if they are distinct occurrences.
                        
                        for loc in locations:
                            result = {
                                "ruleId": check_id,
                                "level": level,
                                "message": {
                                    "text": f"{verdict.title()}: {rationale}\n\nRemediation:\n{remediation}"
                                },
                                "locations": [loc],
                                "properties": {
                                    "verdict": verdict,
                                    "remediation": remediation
                                }
                            }
                            sarif_results.append(result)

        tool_component = {
            "name": "Neuro-Symbolic Software Security",
            "version": "1.0.0",
            "rules": list(rules.values())
        }

        sarif_log = {
            "version": "2.1.0",
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "runs": [
                {
                    "tool": {
                        "driver": tool_component
                    },
                    "results": sarif_results
                }
            ]
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(sarif_log, f, indent=2)
