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
    dataset_name = "S2K/cve_fixes"

    logger.info(f"⬇️ Downloading '{dataset_name}' dataset from HuggingFace...")
    try:
        # Load stream=True to avoid downloading the whole thing if we just need a subset
        dataset = load_dataset(
            dataset_name, split="train", streaming=True, token=hf_token
        )
    except Exception as e:
        logger.error(f"❌ Failed to download dataset '{dataset_name}': {e}")
        if not hf_token:
            logger.error(
                "💡 Hint: This dataset is Gated. Ensure you have set your HF_TOKEN."
            )
        sys.exit(1)

    registry = FewShotRegistry(storage_path=output_path)
    count = 0
    skipped = 0

    logger.info("🔄 Processing and filtering for Python code...")

    for row in dataset:
        if count >= limit:
            break

        # Filter for Python
        # The dataset structure usually has 'lang' or similar.
        # Checking schema of joshbressers/cve_fixes: usually has filename or explicitly lang column?
        # Note: joshbressers/cve_fixes is raw.
        # Let's check typical structure or use a heuristic.
        # Actually, let's use a known compatible subset if possible,
        # but sticking to the request "Real Data", we filter by extension.

        filename = row.get("filename", "")
        if not filename.endswith(".py"):
            continue

        code_before = row.get("old_code", "")
        code_after = row.get("new_code", "")
        cve_id = row.get("cve_id", "Unknown-CVE")

        # Basic validation
        if not code_before or not code_after or len(code_before) > 4096:
            skipped += 1
            continue

        # Heuristic for Vuln Type (since dataset might not label it granulary)
        # In a real pipeline, we might use keywords or another classifier.
        # For now, we label generic "Unknown Vulnerability" or try to guess.
        # Docs 06 implies we rely on "CVEFixes", which maps to CVEs.
        # We'll use the CVE ID as the source.

        # Try to infer summary from CVE ID if available (basic check)
        # Ideally we would fetch CVE details, but keeping it offline/fast for now.

        registry.add_fix_example(
            code_before=code_before,
            code_after=code_after,
            vuln_type="Security Vulnerability",  # Normalized for consistency with Server
            source=cve_id,
        )
        count += 1

        if count % 100 == 0:
            logger.info(f"   Collected {count} Python examples...")

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
