import json
from typing import Dict, Any, Optional
from src.core.ai.cot import extract_cot
from src.core.telemetry import get_logger

logger = get_logger(__name__)


class TeacherGenerator:
    """
    Generates synthetic Chain-of-Thought reasoning using a Teacher LLM (e.g., Gemini 1.5 Pro).
    Used to enrich the training dataset.
    """

    def __init__(self, llm_client, max_retries: int = 2):
        self.client = llm_client
        self.max_retries = max_retries

    def generate(
        self, code: str, vuln_type: str, is_vulnerable: bool
    ) -> Optional[Dict[str, Any]]:
        prompt = self._build_prompt(code, vuln_type, is_vulnerable)

        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.generate(prompt)
                json_part, _ = extract_cot(response)

                # Clean potential markdown
                if json_part.startswith("```json"):
                    json_part = json_part[7:]
                if json_part.endswith("```"):
                    json_part = json_part[:-3]

                data = json.loads(json_part.strip())

                # Basic Validation
                if "is_vulnerable" not in data:
                    raise ValueError("Missing 'is_vulnerable' field")

                return data
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Attempt {attempt+1} failed: {e}")
                if attempt == self.max_retries:
                    logger.error("Max retries reached for teacher generation")
                    return {
                        "analysis_summary": "Generation Failed",
                        "is_vulnerable": is_vulnerable,
                    }
        return None

    def _build_prompt(self, code: str, vuln_type: str, is_vulnerable: bool) -> str:
        truth_str = "VULNERABLE" if is_vulnerable else "SAFE"
        return (
            f"You are a Senior Security Engineer. Analyze this Python code for {vuln_type}.\n\n"
            f"Code Snippet:\n{code}\n\n"
            f"Truth: The code is {truth_str}.\n\n"
            f"Task:\n"
            f"1. Provide a step-by-step reasoning trace in <thinking> tags.\n"
            f"2. Output a valid JSON object describing the security status.\n"
            f"3. Ensure 'is_vulnerable' matches the Truth.\n\n"
            f"Output Schema:\n"
            f"{{\n"
            f'  "is_vulnerable": boolean,\n'
            f'  "risk_level": "LOW"|"MEDIUM"|"HIGH"|"CRITICAL"|"SAFE",\n'
            f'  "analysis_summary": "string",\n'
            f'  "fix_suggestion": "string" or null,\n'
            f'  "secure_code_snippet": "string" or null\n'
            f"}}\n\n"
            f"Do not use Markdown code blocks for the JSON. Start with <thinking>."
        )
