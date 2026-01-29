import json
from typing import Dict, Any, Optional, List
from .base import BaseReporter


class SarifReporter(BaseReporter):
    def generate(
        self,
        results: Dict[str, Any],
        output_path: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Generates a SARIF report from the pipeline results.
        """
        sarif_results: List[Dict[str, Any]] = []
        rules: Dict[str, Dict[str, Any]] = {}

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
                insight_map: Dict[str, Dict[str, Any]] = {}
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
                        verdict = self._normalize_verdict(
                            insight_item.get("verdict", "needs_review")
                        )
                        rationale = insight_item.get("rationale", "")
                        remediation = insight_item.get("remediation", "")
                        confidence = self._extract_confidence(insight_item)
                        fix_description = self._extract_fix_description(insight_item)
                        secure_code = self._extract_secure_code(insight_item)
                    else:
                        verdict = "unverified"
                        rationale = finding.get(
                            "message", "Detected by static analysis."
                        )
                        remediation = "LLM analysis skipped."
                        confidence = None
                        fix_description = None
                        secure_code = None

                    # Determine level based on verdict
                    level = self._level_from_verdict(verdict)

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

                    fixes = self._build_fixes(
                        file_path=file_path,
                        finding=finding,
                        description=fix_description,
                        secure_code=secure_code,
                    )

                    properties: Dict[str, Any] = {
                        "verdict": verdict,
                        "remediation": remediation,
                    }
                    if metadata:
                        graph_report_name = metadata.get("graph_report_name")
                        if graph_report_name:
                            properties["graph_trace"] = graph_report_name
                    if confidence is not None:
                        properties["confidence"] = confidence
                    if rationale:
                        properties["ai_reasoning"] = rationale

                    result = {
                        "ruleId": check_id,
                        "level": level,
                        "message": {
                            "text": self._build_message(
                                verdict=verdict,
                                rationale=rationale,
                                remediation=remediation,
                            )
                        },
                        "locations": [loc],
                        "properties": properties,
                    }
                    if fixes:
                        result["fixes"] = fixes
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

    @staticmethod
    def _normalize_verdict(verdict: str) -> str:
        if not verdict:
            return "unverified"
        return verdict.lower().replace("_", " ").strip()

    @staticmethod
    def _level_from_verdict(verdict: str) -> str:
        verdict_norm = SarifReporter._normalize_verdict(verdict)
        if "true positive" in verdict_norm:
            return "error"
        if "false positive" in verdict_norm:
            return "note"
        if "unverified" in verdict_norm or "needs review" in verdict_norm:
            return "warning"
        return "warning"

    @staticmethod
    def _build_message(verdict: str, rationale: str, remediation: str) -> str:
        rationale_text = rationale or "No rationale provided."
        remediation_text = remediation or "No remediation provided."
        verdict_label = SarifReporter._normalize_verdict(verdict).title()
        return f"{verdict_label}: {rationale_text}\n\nRemediation:\n{remediation_text}"

    @staticmethod
    def _extract_confidence(insight_item: Dict[str, Any]) -> Optional[float]:
        for key in ("confidence", "confidence_score"):
            value = insight_item.get(key)
            if isinstance(value, (int, float)):
                return float(value)
        return None

    @staticmethod
    def _extract_fix_description(insight_item: Dict[str, Any]) -> Optional[str]:
        for key in (
            "fix_suggestion",
            "fix_description",
            "remediation_description",
            "remediation",
            "fix",
        ):
            value = insight_item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _extract_secure_code(insight_item: Dict[str, Any]) -> Optional[str]:
        for key in ("secure_code_snippet", "secure_code", "secure_code_fix"):
            value = insight_item.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return None

    @staticmethod
    def _build_fixes(
        file_path: str,
        finding: Dict[str, Any],
        description: Optional[str],
        secure_code: Optional[str],
    ) -> Optional[List[Dict[str, Any]]]:
        if not description and not secure_code:
            return None

        region = SarifReporter._build_deleted_region(finding, secure_code)
        if not region:
            return None

        fix_entry: Dict[str, Any] = {
            "description": {"text": description or "Apply secure fix."},
            "artifactChanges": [
                {
                    "artifactLocation": {"uri": file_path.replace("\\", "/")},
                    "replacements": [
                        {
                            "deletedRegion": region,
                            "insertedContent": {"text": secure_code or ""},
                        }
                    ],
                }
            ],
        }

        return [fix_entry]

    @staticmethod
    def _build_deleted_region(
        finding: Dict[str, Any], secure_code: Optional[str]
    ) -> Optional[Dict[str, int]]:
        start_line = finding.get("line") or 1
        start_column = finding.get("column") or 1
        end_line = finding.get("end_line") or finding.get("endLine")
        end_column = finding.get("end_column") or finding.get("endColumn")

        if not end_line:
            end_line = start_line
        if not end_column:
            end_column = start_column + 1

        if secure_code:
            first_line = secure_code.splitlines()[0] if secure_code else ""
            if first_line:
                end_column = max(end_column, start_column + len(first_line))

        return {
            "startLine": start_line,
            "startColumn": start_column,
            "endLine": end_line,
            "endColumn": end_column,
        }
