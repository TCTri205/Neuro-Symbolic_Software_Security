import json
from typing import Dict, List, Any


class SecurityPromptBuilder:
    """
    Constructs optimized prompts for LLM-based security analysis.
    """

    SYSTEM_ROLE = (
        "You are an expert Application Security Engineer specializing in Python security analysis. "
        "Your goal is to reduce false positives by analyzing static analysis findings within their execution context. "
        "Do not suggest importing or installing new libraries. "
        "Return only valid JSON without markdown fences or extra text."
    )

    def build_analysis_prompt(
        self, block: Any, snippet: str, file_path: str, ssa_context: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """
        Builds a structured prompt for analyzing security findings in a specific code block.
        """
        findings_json = json.dumps(block.security_findings, indent=2)

        # Calculate approximate lines if block has statements
        start_line = "?"
        end_line = "?"
        if hasattr(block, "statements") and block.statements:
            s = getattr(block.statements[0], "lineno", None)
            e = getattr(block.statements[-1], "end_lineno", None)
            if s:
                start_line = str(s)
            if e:
                end_line = str(e)

        user_content = (
            f"Analyze the following security findings in the provided code snippet.\n\n"
            f"=== CONTEXT ===\n"
            f"File: {file_path}\n"
            f"Scope: {block.scope}\n"
            f"Lines: {start_line}-{end_line}\n\n"
            f"=== DATA FLOW (SSA) ===\n"
            f"Phi Nodes: {ssa_context.get('phi_nodes', [])}\n"
            f"Definitions: {json.dumps(ssa_context.get('defs', []), indent=1)}\n"
            f"Uses: {json.dumps(ssa_context.get('uses', []), indent=1)}\n\n"
            f"=== FINDINGS ===\n"
            f"{findings_json}\n\n"
            f"=== CODE SNIPPET ===\n"
            f"```python\n"
            f"{snippet}\n"
            f"```\n\n"
            f"=== INSTRUCTIONS ===\n"
            f"1. Trace the data flow for variables involved in the findings.\n"
            f"2. Determine if input validation or sanitization occurs before the sink.\n"
            f"3. Classify each finding as 'True Positive', 'False Positive', or 'Needs Review'.\n"
            f"4. If a finding is a True Positive, provide fix_suggestion and secure_code_snippet. Preserve original indentation.\n"
            f"5. If not vulnerable, set fix_suggestion and secure_code_snippet to null.\n"
            f"6. IMPORTANT: Return ONLY valid JSON. No markdown code blocks around the JSON.\n\n"
            f"=== OUTPUT FORMAT ===\n"
            f"{{\n"
            f'  "analysis": [\n'
            f"    {{\n"
            f'      "check_id": "<id from findings>",\n'
            f'      "verdict": "<classification>",\n'
            f'      "rationale": "<concise explanation>",\n'
            f'      "remediation": "<code fix or \'N/A\'>",\n'
            f'      "fix_suggestion": "<description or null>",\n'
            f'      "secure_code_snippet": "<fixed code or null>",\n'
            f'      "confidence_score": 0.0,\n'
            f'      "risk_level": "LOW|MEDIUM|HIGH|CRITICAL|SAFE",\n'
            f'      "reasoning_trace": "<short reasoning>",\n'
            f'      "analysis_summary": "<concise summary>"\n'
            f"    }}\n"
            f"  ]\n"
            f"}}"
        )

        return [
            {"role": "system", "content": self.SYSTEM_ROLE},
            {"role": "user", "content": user_content},
        ]
