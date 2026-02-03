#!/usr/bin/env python3
"""
Data Preparation Script for NSSS Security Auditor.

Fetches real vulnerability data (CVEFixes) from HuggingFace,
filters for Python, and populates the FewShotRegistry for training.

Reference: Docs 06 - Data Factory Strategy.
"""

import argparse
import logging
import sys
from pathlib import Path

# Ensure src is in path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.core.finetuning.few_shot_registry import FewShotRegistry  # noqa: E402
from src.core.telemetry import get_logger  # noqa: E402

logger = get_logger(__name__)


import os


def prepare_data(output_path: Path, limit: int = 5000):
    """
    Downloads and processes CVEFixes dataset.
    """
    try:
        from datasets import load_dataset
    except ImportError:
        logger.error(
            "❌ 'datasets' library not found. Please run: pip install datasets"
        )
        sys.exit(1)

    hf_token = os.getenv("HF_TOKEN")

    # Use bigcode/commitpackft as the primary source for real-world fixes
    # This dataset is Public, huge, and multi-language. We will filter for Python fixes.
    dataset_name = "bigcode/commitpackft"

    try:
        logger.info(f"⬇️ Streaming '{dataset_name}' from HuggingFace...")
        # Streaming is crucial here because the dataset is 1TB+
        dataset = load_dataset(
            dataset_name, split="train", streaming=True, token=hf_token
        )
    except Exception as e:
        logger.error(f"❌ Failed to load '{dataset_name}': {e}")
        if not hf_token:
            logger.error(
                "💡 Hint: Ensure you have internet access. HF_TOKEN is optional for this public dataset."
            )
        sys.exit(1)

    registry = FewShotRegistry(storage_path=output_path)
    count = 0
    skipped = 0
    checked = 0

    logger.info(f"🔄 Filtering '{dataset_name}' for Python Security Fixes...")
    logger.info("   Keywords: cve, security, vuln, fix, patch")

    # Security keywords to filter commit messages
    keywords = ["cve", "security", "vuln", "fix", "patch", "close", "resolve"]

    for row in dataset:
        if count >= limit:
            break

        checked += 1
        if checked % 1000 == 0:
            logger.info(f"   Scanned {checked} commits... (Found {count} examples)")

        # 1. Filter by Language
        lang = row.get("lang", "") or row.get("language", "")
        if not lang or lang.lower() != "python":
            continue

        # 2. Filter by Message (Heuristic for Fixes)
        message = row.get("message", "").lower()
        if not any(k in message for k in keywords):
            continue

        # 3. Get Code
        code_before = row.get("old_contents", "")
        code_after = row.get("new_contents", "")

        # Validate content
        if not code_before or not code_after:
            continue

        if len(code_before) > 4096 or len(code_after) > 4096:
            # Skip too long files to fit in context
            skipped += 1
            continue

        # Basic diff check (avoid identical files)
        if code_before == code_after:
            continue

        # Create Example
        # Try to extract CVE ID if present
        import re

        cve_match = re.search(r"cve-\d{4}-\d+", message)
        source_id = cve_match.group(0).upper() if cve_match else "Real-World-Fix"

        registry.add_fix_example(
            code_before=code_before,
            code_after=code_after,
            vuln_type="Potential Security Vulnerability"
            if "security" in message or "cve" in message
            else "Bug Fix",
            source=source_id,
        )

        count += 1

    logger.info("✅ Processing complete.")
    logger.info(f"   Total Examples: {count}")
    logger.info(f"   Scanned: {checked}")
    logger.info(f"   Skipped (Length/Duplicate): {skipped}")

    registry.save()


def main():
    parser = argparse.ArgumentParser(description="Prepare real CVE data for training")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/few_shot_registry.json"),
        help="Path to save the registry",
    )
    parser.add_argument(
        "--limit", type=int, default=2000, help="Maximum number of examples to fetch"
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(level=logging.INFO)

    prepare_data(args.output, args.limit)


if __name__ == "__main__":
    main()
