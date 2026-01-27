"""
Few-Shot Registry for storing security examples (fix samples, false positives, verified vulnerabilities).
Implements the Knowledge Base pattern described in Doc 03 (Data Strategy) Section 4.
"""

import dataclasses
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Literal

from src.core.telemetry import get_logger

logger = get_logger(__name__)


@dataclasses.dataclass
class FewShotExample:
    """
    A single few-shot example for prompt engineering and continuous learning.

    Attributes:
        code: The code snippet
        vuln_type: Vulnerability type (SQL Injection, XSS, etc.)
        is_vulnerable: Ground truth label
        example_type: fix/false_positive/positive
        metadata: Additional context (reasoning, source, etc.)
        content_hash: SHA-256 hash for duplicate detection
        timestamp: When the example was added
    """

    code: str
    vuln_type: str
    is_vulnerable: bool
    example_type: Literal["fix", "false_positive", "positive"]
    metadata: Dict[str, Any]
    content_hash: str
    timestamp: str


class FewShotRegistry:
    """
    Storage and retrieval system for few-shot examples.

    Purpose:
    - Store CVE fix samples (code_before/code_after pairs)
    - Store false positives from interactive triage (Doc 03, Section 4)
    - Store verified positive examples with reasoning
    - Support conversion to training dataset format

    Usage:
        registry = FewShotRegistry()
        registry.add_fix_example(code_before, code_after, "SQL Injection", "CVE-2024-001")
        registry.save()

        # Later: Retrieve examples for few-shot prompting
        examples = registry.get_examples(vuln_type="SQL Injection", limit=3)
    """

    def __init__(self, storage_path: Optional[Path] = None):
        """
        Initialize the registry.

        Args:
            storage_path: Path to JSON file for persistence (default: data/few_shot_registry.json)
        """
        self.storage_path = storage_path or Path("data/few_shot_registry.json")
        self.examples: List[FewShotExample] = []
        self._content_hashes: set[str] = set()

    def add_fix_example(
        self, code_before: str, code_after: str, vuln_type: str, source: str
    ) -> None:
        """
        Add a CVE fix pair (vulnerable code + patched code).

        Args:
            code_before: Vulnerable code snippet
            code_after: Fixed/patched code snippet
            vuln_type: Type of vulnerability addressed
            source: Source identifier (e.g., "CVEFixes-2024-001")
        """
        # Add vulnerable example
        self._add_example(
            code=code_before,
            vuln_type=vuln_type,
            is_vulnerable=True,
            example_type="fix",
            metadata={
                "source": source,
                "fix_available": True,
                "fixed_code": code_after,
            },
        )

        # Add fixed example (negative sample)
        self._add_example(
            code=code_after,
            vuln_type=vuln_type,
            is_vulnerable=False,
            example_type="fix",
            metadata={"source": source, "is_patch": True, "original_code": code_before},
        )

    def add_false_positive(
        self, code: str, vuln_type: str, reason: str, triaged_by: str
    ) -> None:
        """
        Add a false positive from interactive triage (Doc 03, Section 4: Feedback Loop).

        Args:
            code: Code that was incorrectly flagged as vulnerable
            vuln_type: The vulnerability type that was incorrectly detected
            reason: Explanation why it's a false positive
            triaged_by: Identifier of the analyst who marked it
        """
        self._add_example(
            code=code,
            vuln_type=vuln_type,
            is_vulnerable=False,
            example_type="false_positive",
            metadata={
                "reason": reason,
                "triaged_by": triaged_by,
                "triage_timestamp": datetime.now().isoformat(),
            },
        )

    def add_positive_example(
        self, code: str, vuln_type: str, reasoning: str, source: str
    ) -> None:
        """
        Add a verified vulnerability with expert reasoning (for CoT training).

        Args:
            code: Vulnerable code snippet
            vuln_type: Type of vulnerability
            reasoning: Chain-of-thought explanation
            source: Source of the example (e.g., "Manual Review", "Penetration Test")
        """
        self._add_example(
            code=code,
            vuln_type=vuln_type,
            is_vulnerable=True,
            example_type="positive",
            metadata={"reasoning": reasoning, "source": source},
        )

    def _add_example(
        self,
        code: str,
        vuln_type: str,
        is_vulnerable: bool,
        example_type: Literal["fix", "false_positive", "positive"],
        metadata: Dict[str, Any],
    ) -> None:
        """Internal method to add an example with duplicate detection."""
        # Generate content hash for deduplication
        content_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()

        if content_hash in self._content_hashes:
            logger.debug(f"Duplicate example detected (hash: {content_hash[:8]}...)")
            return

        example = FewShotExample(
            code=code,
            vuln_type=vuln_type,
            is_vulnerable=is_vulnerable,
            example_type=example_type,
            metadata=metadata,
            content_hash=content_hash,
            timestamp=datetime.now().isoformat(),
        )

        self.examples.append(example)
        self._content_hashes.add(content_hash)

    def get_examples(
        self,
        vuln_type: Optional[str] = None,
        example_type: Optional[Literal["fix", "false_positive", "positive"]] = None,
        limit: Optional[int] = None,
    ) -> List[FewShotExample]:
        """
        Retrieve examples with optional filtering.

        Args:
            vuln_type: Filter by vulnerability type
            example_type: Filter by example type (fix/false_positive/positive)
            limit: Maximum number of examples to return

        Returns:
            List of matching examples (most recent first)
        """
        results = self.examples

        if vuln_type:
            results = [ex for ex in results if ex.vuln_type == vuln_type]

        if example_type:
            results = [ex for ex in results if ex.example_type == example_type]

        # Sort by timestamp (most recent first)
        results = sorted(results, key=lambda x: x.timestamp, reverse=True)

        if limit:
            results = results[:limit]

        return results

    def save(self) -> None:
        """Persist registry to disk (JSON format)."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0",
            "examples": [dataclasses.asdict(ex) for ex in self.examples],
        }

        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(self.examples)} examples to {self.storage_path}")

    def load(self) -> None:
        """Load registry from disk."""
        if not self.storage_path.exists():
            logger.warning(f"Registry file not found: {self.storage_path}")
            return

        with open(self.storage_path, encoding="utf-8") as f:
            data = json.load(f)

        self.examples = []
        self._content_hashes = set()

        for ex_dict in data.get("examples", []):
            example = FewShotExample(**ex_dict)
            self.examples.append(example)
            self._content_hashes.add(example.content_hash)

        logger.info(f"Loaded {len(self.examples)} examples from {self.storage_path}")

    def to_training_format(
        self, vuln_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Convert examples to training dataset format (Doc 06, Section 3.2).

        Format aligns with the Client-Server Protocol (Doc 05a):
        {
            "instruction": str,
            "input": {"function_signature": str, "vulnerability_type": str, "context": {...}},
            "output": {"is_vulnerable": bool, "risk_level": str, ...}
        }

        Args:
            vuln_type: Optional filter by vulnerability type

        Returns:
            List of training examples in Alpaca/ChatML format
        """
        examples = self.get_examples(vuln_type=vuln_type)
        training_data = []

        for ex in examples:
            # Build input (Client Protocol format)
            input_obj = {
                "function_signature": ex.code,
                "vulnerability_type": ex.vuln_type,
                "context": {
                    "sanitizers_found": []  # Can be enriched from metadata
                },
            }

            # Build output (Server Response format)
            output_obj = {
                "is_vulnerable": ex.is_vulnerable,
                "confidence_score": 1.0,  # Ground truth has full confidence
                "risk_level": "CRITICAL" if ex.is_vulnerable else "SAFE",
                "analysis_summary": ex.metadata.get(
                    "reasoning",
                    f"Code is {'vulnerable' if ex.is_vulnerable else 'safe'}",
                ),
                "fix_suggestion": ex.metadata.get("fixed_code")
                if ex.is_vulnerable
                else None,
                "secure_code_snippet": ex.metadata.get("fixed_code")
                if ex.is_vulnerable
                else None,
                "constraint_check": {"syntax_valid": True, "logic_sound": True},
            }

            training_data.append(
                {
                    "instruction": f"Analyze the following Python code trace for {ex.vuln_type} vulnerabilities. Return logic in JSON.",
                    "input": input_obj,
                    "output": output_obj,
                }
            )

        return training_data
