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

    # Try multiple dataset sources in order of preference
    dataset_sources = [
        "diversevul/diversevul",  # Public vulnerability detection dataset
        "bigcode/the-stack-smol",  # Backup: general code dataset (large)
    ]

    dataset = None
    dataset_name = None

    for source in dataset_sources:
        try:
            logger.info(f"⬇️ Attempting to download '{source}' from HuggingFace...")
            dataset = load_dataset(
                source, split="train", streaming=True, token=hf_token
            )
            dataset_name = source
            logger.info(f"✅ Successfully loaded dataset: {source}")
            break
        except Exception as e:
            logger.warning(f"⚠️ Failed to load '{source}': {e}")
            continue

    if dataset is None:
        logger.error("❌ Failed to download any available dataset.")
        logger.error("💡 Tried sources: " + ", ".join(dataset_sources))
        if not hf_token:
            logger.error(
                "💡 Some datasets may be Gated. Set HF_TOKEN if you have access."
            )
        sys.exit(1)

    registry = FewShotRegistry(storage_path=output_path)
    count = 0
    skipped = 0

    logger.info(
        f"🔄 Processing dataset '{dataset_name}' and filtering for Python vulnerabilities..."
    )

    for row in dataset:
        if count >= limit:
            break

        # Handle different dataset schemas
        if dataset_name == "diversevul/diversevul":
            # DiverseVul schema: func (code), target (0=safe, 1=vulnerable), cwe (CWE-ID)
            code = row.get("func", "")
            is_vulnerable = row.get("target", 0) == 1
            cwe_id = row.get("cwe", "Unknown-CWE")

            # Skip non-vulnerable or invalid entries
            if not is_vulnerable or not code or len(code) > 4096:
                skipped += 1
                continue

            # For vulnerabilities, create a "before fix" example
            # Since we don't have the fixed version, we'll use this for detection training
            registry.add_positive_example(
                code=code,
                vuln_type="Security Vulnerability",
                reasoning=f"Code contains vulnerability (CWE: {cwe_id})",
                source=f"DiverseVul-{cwe_id}",
            )

        elif dataset_name == "bigcode/the-stack-smol":
            # The Stack schema: content (code), language
            # Filter for Python and create examples
            lang = row.get("lang", "")
            if lang.lower() != "python":
                continue

            code = row.get("content", "")
            if not code or len(code) > 4096:
                skipped += 1
                continue

            # Since this is general code, we'll use it as safe examples
            # Skip for now as we want vulnerability data
            continue

        else:
            # Unknown schema - try generic approach
            filename = row.get("filename", "")
            if not filename.endswith(".py"):
                continue

            code_before = row.get("old_code", row.get("code_before", ""))
            code_after = row.get("new_code", row.get("code_after", ""))

            if not code_before or not code_after or len(code_before) > 4096:
                skipped += 1
                continue

            cve_id = row.get("cve_id", row.get("id", "Unknown-CVE"))

            registry.add_fix_example(
                code_before=code_before,
                code_after=code_after,
                vuln_type="Security Vulnerability",
                source=cve_id,
            )

        count += 1

        if count % 100 == 0:
            logger.info(f"   Collected {count} examples...")

    logger.info("✅ Processing complete.")
    logger.info(f"   Total Examples: {count}")
    logger.info(f"   Skipped/Filtered: {skipped}")

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
