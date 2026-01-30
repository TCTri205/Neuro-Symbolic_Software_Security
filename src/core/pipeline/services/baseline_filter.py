from typing import Dict, List, Optional, Tuple

from src.core.pipeline.interfaces import BaselineEnginePort
from src.core.scan.secrets import SecretMatch


class BaselineFilterService:
    def __init__(self, baseline_engine: BaselineEnginePort, logger) -> None:
        self.baseline_engine = baseline_engine
        self.logger = logger

    def filter_findings(
        self,
        cfg,
        file_path: str,
        source_lines: List[str],
        secrets: Optional[List[SecretMatch]] = None,
    ) -> Tuple[Dict[str, int], List[SecretMatch]]:
        new_count = 0
        existing_count = 0

        for block in cfg._blocks.values():
            if not block.security_findings:
                continue
            filtered, stats = self.baseline_engine.filter_findings(
                block.security_findings, file_path, source_lines
            )
            block.security_findings = filtered
            new_count += stats.get("new", 0)
            existing_count += stats.get("existing", 0)

        filtered_secrets: List[SecretMatch] = []
        if secrets:
            secret_findings = []
            for s in secrets:
                secret_findings.append(
                    {
                        "check_id": f"secret.{s.type.replace(' ', '_').lower()}",
                        "message": f"Found {s.type}",
                        "line": s.line,
                        "column": 1,
                        "severity": "CRITICAL",
                        "_original_secret": s,
                    }
                )

            filtered_dicts, stats = self.baseline_engine.filter_findings(
                secret_findings, file_path, source_lines
            )

            for d in filtered_dicts:
                if "_original_secret" in d:
                    filtered_secrets.append(d["_original_secret"])

            new_count += stats.get("new", 0)
            existing_count += stats.get("existing", 0)
        elif secrets is not None:
            filtered_secrets = []

        stats = {
            "total": new_count + existing_count,
            "new": new_count,
            "existing": existing_count,
            "resolved": 0,
        }
        return stats, filtered_secrets
