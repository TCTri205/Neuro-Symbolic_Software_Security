import os
from typing import Any, Dict, List, Optional, Tuple, Type

from src.core.parser.obfuscation import detect_obfuscation
from src.core.pipeline.interfaces import (
    SecretScannerPort,
    SemgrepRunnerPort,
    StaticScanPort,
)
from src.core.scan.secrets import SecretMatch, SecretScanner
from src.core.scan.semgrep import SemgrepRunner
from src.core.telemetry import MeasureLatency


class StaticScanService(StaticScanPort):
    def __init__(
        self,
        logger,
        semgrep_config: Optional[str] = None,
        semgrep_runner_cls: Type[SemgrepRunner] = SemgrepRunner,
        secret_scanner: Optional[SecretScannerPort] = None,
        semgrep_runner: Optional[SemgrepRunnerPort] = None,
    ) -> None:
        self.logger = logger
        self.secret_scanner = secret_scanner or SecretScanner()
        if semgrep_config is None:
            rules_path = os.path.join(os.getcwd(), "rules", "nsss-python-owasp.yml")
            semgrep_config = rules_path if os.path.exists(rules_path) else "auto"
        self.semgrep_runner = semgrep_runner or semgrep_runner_cls(
            config=semgrep_config
        )

    def scan_secrets(self, source_code: str) -> Tuple[List[SecretMatch], Optional[str]]:
        try:
            with MeasureLatency("scan_secrets"):
                return self.secret_scanner.scan(source_code), None
        except Exception as e:
            msg = f"Secret scanning failed: {e}"
            self.logger.error(msg)
            return [], msg

    def scan_semgrep(self, file_path: str) -> Tuple[Dict[str, Any], Optional[str]]:
        if not file_path or file_path == "<unknown>":
            return {}, None
        try:
            with MeasureLatency("semgrep_scan"):
                return self.semgrep_runner.run(file_path), None
        except Exception as e:
            msg = f"Semgrep scan failed: {e}"
            self.logger.error(msg)
            return {}, msg

    def check_obfuscation(self, source_code: str) -> Tuple[bool, List[str]]:
        return detect_obfuscation(source_code)
