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
                # We care about blocks that have LLM insights (which implies they had findings)
                llm_insights = block.get("llm_insights", [])
                
                for insight in llm_insights:
                    # Each insight might contain multiple analysis items (one per finding usually)
                    analysis_list = insight.get("analysis", [])
                    if not analysis_list:
                        # Fallback if analysis is missing but we have response text
                        pass
                        
                    snippet = insight.get("snippet", "")
                    
                    for item in analysis_list:
                        verdict = item.get("verdict", "Unknown")
                        # Only report actionable findings or everything? Let's report everything but highlight True Positives.
                        
                        finding_detail = {
                            "check_id": item.get("check_id", "Unknown"),
                            "verdict": verdict,
                            "rationale": item.get("rationale", "No rationale provided."),
                            "remediation": item.get("remediation", "No remediation provided."),
                            "snippet": snippet,
                            "block_id": block.get("id"),
                            "scope": block.get("scope")
                        }
                        file_findings.append(finding_detail)
            
            if file_findings:
                has_findings = True
                content.append(f"## File: `{file_path}`\n")
                
                for i, f in enumerate(file_findings, 1):
                    icon = "🔴" if f["verdict"].lower() == "true positive" else "⚪"
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
