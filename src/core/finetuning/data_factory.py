import json
import ast
import dataclasses
from typing import List, Dict, Any, Optional, Set
from src.core.privacy.masker import PrivacyMasker
from src.core.finetuning.teacher import TeacherGenerator


@dataclasses.dataclass
class TrainingExample:
    instruction: str
    input_data: str
    output_data: Dict[str, Any]


class DataFactory:
    """
    Constructs high-quality training datasets for Neuro-Symbolic Security Models.
    Implements the 'Data Factory' pattern:
    1. Preprocessing (Filtering)
    2. Hard Negatives (Code Fixes)
    3. Neuro-Symbolic Augmentation (Masking, Simulated Context)
    4. Teacher Reasoning (Synthetic CoT)
    """

    def __init__(self, teacher_model=None):
        """
        Args:
            teacher_model: An LLMClient instance (or mock) to generate synthetic reasoning.
        """
        if teacher_model:
            self.teacher = TeacherGenerator(teacher_model)
        else:
            self.teacher = None
        self.masker = PrivacyMasker(preserve_builtins=True)

    def process_row(self, row: Dict[str, str]) -> List[TrainingExample]:
        """
        Process a single row from CVEFixes dataset.
        Row format: {"code_before": str, "code_after": str, "vuln_type": str, ...}
        """
        examples = []
        vuln_type = row.get("vuln_type", "Unknown Vulnerability")

        # 1. Positive Sample (Vulnerable)
        if row.get("code_before"):
            pos_example = self._create_example(
                code=row["code_before"], vuln_type=vuln_type, is_vulnerable=True
            )
            if pos_example:
                examples.append(pos_example)

        # 2. Negative Sample (Fixed)
        if row.get("code_after"):
            neg_example = self._create_example(
                code=row["code_after"], vuln_type=vuln_type, is_vulnerable=False
            )
            if neg_example:
                examples.append(neg_example)

        return examples

    def _create_example(
        self, code: str, vuln_type: str, is_vulnerable: bool
    ) -> Optional[TrainingExample]:
        # 1. Privacy Masking (Typed)
        sensitive_vars = self._extract_sensitive_vars(code)
        try:
            masked_code, _ = self.masker.mask(code, sensitive_vars=sensitive_vars)
        except SyntaxError:
            # Skip invalid code
            return None

        # 2. Build Input JSON (Client Protocol)
        input_obj = {
            "function_signature": masked_code,
            "vulnerability_type": vuln_type,
            "context": {
                "sanitizers_found": []  # Simulation: Empty for training (or randomize?)
            },
        }
        input_str = json.dumps(input_obj, indent=2)

        # 3. Generate Output (Teacher Reasoning)
        output_obj = self._generate_output(code, vuln_type, is_vulnerable)

        # 4. Final Example
        return TrainingExample(
            instruction=f"Analyze the following Python code trace for {vuln_type} vulnerabilities. Return logic in JSON.",
            input_data=input_str,
            output_data=output_obj,
        )

    def _extract_sensitive_vars(self, code: str) -> Set[str]:
        """Heuristic: Treat function arguments as sensitive user input."""
        sensitive = set()
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for arg in node.args.args:
                        sensitive.add(arg.arg)
        except Exception:
            pass
        return sensitive

    def _generate_output(
        self, code: str, vuln_type: str, is_vulnerable: bool
    ) -> Dict[str, Any]:
        """
        Uses Teacher Model to generate reasoning and structured analysis.
        Fallback to template if no teacher available.
        """
        if self.teacher:
            result = self.teacher.generate(code, vuln_type, is_vulnerable)
            if result:
                return result

        # Fallback / Template
        return {
            "is_vulnerable": is_vulnerable,
            "confidence_score": 1.0,
            "risk_level": "CRITICAL" if is_vulnerable else "SAFE",
            "reasoning_trace": f"Initial scan detected {vuln_type} pattern. Verified lack of sanitization in data flow.",
            "analysis_summary": f"Code is {'vulnerable' if is_vulnerable else 'safe'} regarding {vuln_type}.",
            "fix_suggestion": "Apply proper validation and sanitization."
            if is_vulnerable
            else None,
            "secure_code_snippet": None,
            "constraint_check": {"syntax_valid": True, "logic_sound": True},
        }
