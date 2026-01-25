from typing import Dict, Any
from .base import BaseReporter

class MarkdownReporter(BaseReporter):
    def generate(self, results: Dict[str, Any], output_path: str) -> None:
        """
        Generates a Markdown report from the pipeline results.
        """
        content = ["# Neuro-Symbolic Security Scan Report\n"]
        
        has_findings = False
        
        for file_path, file_data in results.items():
            file_findings = []
            
            # Check for error in file processing
            if "error" in file_data:
                content.append(f"## File: `{file_path}`")
                content.append(f"**Error during scan**: {file_data['error']}\n")
                continue
                
            structure = file_data.get("structure", {})
            blocks = structure.get("blocks", [])
            
            for block in blocks:
                # Get raw findings and insights
                security_findings = block.get("security_findings", [])
                llm_insights = block.get("llm_insights", [])
                
                # Create a map of insights by check_id (if possible) or just process list
                # Since LLM insights are usually 1-to-1 or 1-to-many with findings, 
                # but the current structure appends a single insight object per LLM call.
                # If LLM ran, we use its output. If not, we use raw findings.
                
                if llm_insights:
                    for insight in llm_insights:
                        # Each insight might contain multiple analysis items
                        analysis_list = insight.get("analysis", [])
                        snippet = insight.get("snippet", "")
                        
                        if not analysis_list:
                             continue

                        for item in analysis_list:
                            verdict = item.get("verdict", "Unknown")
                            verdict_norm = verdict.lower().replace("_", " ")
                            
                            finding_detail = {
                                "check_id": item.get("check_id", "Unknown"),
                                "verdict": verdict,
                                "verdict_norm": verdict_norm,
                                "rationale": item.get("rationale", "No rationale provided."),
                                "remediation": item.get("remediation", "No remediation provided."),
                                "snippet": snippet,
                                "block_id": block.get("id"),
                                "scope": block.get("scope")
                            }
                            file_findings.append(finding_detail)
                elif security_findings:
                    # Fallback to raw findings if no LLM analysis
                    for finding in security_findings:
                        finding_detail = {
                            "check_id": finding.get("check_id", "Unknown"),
                            "verdict": "Unverified (Static Analysis)",
                            "verdict_norm": "unverified",
                            "rationale": finding.get("message", "No message provided."),
                            "remediation": "No remediation available (LLM disabled).",
                            "snippet": "", 
                            "block_id": block.get("id"),
                            "scope": block.get("scope")
                        }
                        file_findings.append(finding_detail)
            
            if file_findings:
                has_findings = True
                content.append(f"## File: `{file_path}`\n")
                
                for i, f in enumerate(file_findings, 1):
                    icon = "🔴" if "true positive" in f["verdict_norm"] else "⚪"
                    content.append(f"### {i}. {f['check_id']} {icon}")
                    content.append(f"**Verdict**: {f['verdict']}")
                    content.append(f"**Scope**: `{f['scope']}` (Block {f['block_id']})")
                    content.append(f"\n**Rationale**:\n{f['rationale']}\n")
                    
                    if f["snippet"]:
                        content.append(f"**Vulnerable Code**:\n```python\n{f['snippet']}\n```\n")
                    
                    if f["remediation"]:
                        content.append(f"**Remediation**:\n```python\n{f['remediation']}\n```\n")
                    
                    content.append("---\n")
        
        if not has_findings:
            content.append("\n✅ No security issues found (or no files scanned).\n")
            
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(content))
