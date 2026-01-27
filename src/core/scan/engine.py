import os
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from src.core.scan.semgrep import SemgrepRunner
from src.core.telemetry import get_logger

logger = get_logger(__name__)


class Finding(BaseModel):
    check_id: str
    path: str
    line: int
    column: int
    message: str
    severity: str
    metadata: Dict[str, Any] = {}


class RuleEngine:
    def __init__(self, rules_path: Optional[str] = None):
        if rules_path:
            self.rules_path = rules_path
        else:
            # Default to bundled rules
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.rules_path = os.path.join(base_dir, "rules", "python_security.yaml")

        self.runner = SemgrepRunner(config=self.rules_path)

    def scan_file(self, file_path: str) -> List[Finding]:
        if not os.path.exists(self.rules_path):
            logger.error(f"Rule file not found: {self.rules_path}")
            return []

        result = self.runner.run(file_path)

        if "error" in result:
            logger.error(f"Semgrep failed for {file_path}: {result['error']}")
            return []

        findings = []
        for res in result.get("results", []):
            try:
                findings.append(
                    Finding(
                        check_id=res["check_id"],
                        path=res["path"],
                        line=res["start"]["line"],
                        column=res["start"]["col"],
                        message=res["extra"]["message"],
                        severity=res["extra"]["severity"],
                        metadata=res["extra"].get("metadata", {}),
                    )
                )
            except Exception as e:
                logger.error(f"Failed to parse finding: {e}")

        return findings
