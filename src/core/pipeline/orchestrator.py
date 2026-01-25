from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import logging

from src.core.cfg.builder import CFGBuilder
from src.core.scan.secrets import SecretScanner, SecretMatch
from src.core.privacy.masker import PrivacyMasker
from src.core.analysis.sanitizers import SanitizerRegistry
from src.core.telemetry import get_logger, MeasureLatency


@dataclass
class AnalysisResult:
    file_path: str
    cfg: Optional[Any] = None  # Replace with actual CFG type when available/imported
    secrets: List[SecretMatch] = field(default_factory=list)
    masked_code: Optional[str] = None
    mask_mapping: Optional[Dict[str, str]] = None
    errors: List[str] = field(default_factory=list)


class AnalysisOrchestrator:
    """
    Orchestrates the security analysis pipeline:
    1. Static Scanning (Secrets)
    2. CFG Construction
    3. Privacy Masking (for external analysis)
    """

    def __init__(self):
        self.secret_scanner = SecretScanner()
        self.privacy_masker = PrivacyMasker()
        # CFGBuilder is instantiated per file usually, or we can reuse logic?
        # Based on builder.py, it seems stateful per build.
        self.sanitizer_registry = SanitizerRegistry()
        self.logger = get_logger(__name__)

    def analyze_code(
        self, source_code: str, file_path: str = "<unknown>"
    ) -> AnalysisResult:
        result = AnalysisResult(file_path=file_path)

        # Step 1: Secret Scanning (on original code)
        try:
            with MeasureLatency("scan_secrets"):
                result.secrets = self.secret_scanner.scan(source_code)
        except Exception as e:
            msg = f"Secret scanning failed: {e}"
            self.logger.error(msg)
            result.errors.append(msg)

        # Step 2: CFG Construction
        try:
            with MeasureLatency("build_cfg"):
                import ast

                tree = ast.parse(source_code)
                builder = CFGBuilder()
                # Use module name derived from file path or default
                module_name = file_path.split("/")[-1].replace(".py", "")
                result.cfg = builder.build(module_name, tree)
        except Exception as e:
            msg = f"CFG construction failed: {e}"
            self.logger.error(msg)
            result.errors.append(msg)

        # Step 3: Privacy Masking (Optional/Always? Let's do it to have it ready)
        # In a real scenario, this might be triggered only if we send to LLM.
        # For now, we execute it to verify the pipeline capability.
        try:
            with MeasureLatency("privacy_masking"):
                masked_code, mapping = self.privacy_masker.mask(source_code)
                result.masked_code = masked_code
                result.mask_mapping = mapping
        except Exception as e:
            msg = f"Privacy masking failed: {e}"
            self.logger.error(msg)
            result.errors.append(msg)

        return result

    def analyze_file(self, file_path: str) -> AnalysisResult:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source_code = f.read()
            return self.analyze_code(source_code, file_path)
        except Exception as e:
            self.logger.error(f"Failed to read file {file_path}: {e}")
            return AnalysisResult(file_path=file_path, errors=[f"File read error: {e}"])
