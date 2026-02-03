#!/usr/bin/env python3
"""
Data Preparation Script for NSSS Security Auditor.

Fetches real Python code from The Stack dataset on HuggingFace,
detects security vulnerability patterns, and populates the FewShotRegistry for training.

This script scans real-world Python code from GitHub and identifies potential
security vulnerabilities based on code patterns (SQL injection, eval, pickle, etc.).

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

    # List of datasets to try (in order of preference)
    # 1. bigcode/the-stack-smol: High quality, requires auth (Gated)
    # 2. codeparrot/codeparrot-clean: Good quality Python code, usually public/easier access
    dataset_candidates = [
        "bigcode/the-stack-smol",
        "codeparrot/codeparrot-clean",
    ]

    dataset = None
    dataset_name = ""

    for candidate in dataset_candidates:
        try:
            logger.info(f"⬇️ Attempting to load '{candidate}' from HuggingFace...")
            # Streaming is crucial for these large datasets
            dataset = load_dataset(
                candidate,
                split="train",
                streaming=True,
                token=hf_token,
                trust_remote_code=True,  # Some datasets might need this
            )
            dataset_name = candidate
            logger.info(f"✅ Successfully connected to '{candidate}'")
            break
        except Exception as e:
            logger.warning(f"⚠️ Failed to load '{candidate}': {e}")
            if "gated" in str(e).lower() and not hf_token:
                logger.warning(
                    "   (This dataset requires an HF_TOKEN. Check your notebook settings)"
                )
            continue

    if dataset is None:
        logger.error("❌ Failed to load any candidate datasets.")
        logger.error("💡 Please check your HF_TOKEN and internet connection.")
        sys.exit(1)

    registry = FewShotRegistry(storage_path=output_path)
    count = 0
    skipped = 0
    checked = 0

    logger.info(
        f"🔄 Filtering '{dataset_name}' for Python files with security patterns..."
    )
    logger.info("   Looking for: SQL injection, XSS, eval, pickle, yaml.load patterns")

    # Security vulnerability patterns in code
    vuln_patterns = [
        ("SQL Injection", ["execute(", "cursor.execute", "%s", "f'SELECT", "format("]),
        (
            "Code Injection",
            ["eval(", "exec(", "subprocess.call", "os.system", "input("],
        ),
        (
            "Insecure Deserialization",
            ["pickle.load", "yaml.load", "json.load", "unpickle"],
        ),
        ("Path Traversal", ["open(user_input)", "../../", "os.path.join(user_input)"]),
        ("XSS", ["render_template", "{{ user_input }}", "html +=", "innerHTML"]),
    ]

    for row in dataset:
        if count >= limit:
            break

        checked += 1
        if checked % 1000 == 0:
            logger.info(
                f"   Scanned {checked} files... (Found {count} vulnerable examples)"
            )

        # 1. Filter by Language (Only for multi-language datasets like 'the-stack')
        # 'codeparrot' datasets are Python-only by definition, so we skip this check for them.
        if "codeparrot" not in dataset_name:
            lang = row.get("lang", "") or row.get("language", "")
            if not lang or lang.lower() != "python":
                continue

        # 2. Get Code Content
        code = row.get("content", "")
        if not code or len(code) < 100 or len(code) > 4096:
            skipped += 1
            continue

        # 3. Detect Vulnerability Patterns
        detected_vuln = None
        for vuln_name, patterns in vuln_patterns:
            if any(pattern in code for pattern in patterns):
                detected_vuln = vuln_name
                break

        if not detected_vuln:
            continue

        # Create Example - use the vulnerable code as 'before'
        # For 'after', we'll create a simple fix template
        source_id = row.get("max_stars_repo_name", row.get("path", "Unknown"))

        # For training, we use the vulnerable code as the example
        # The model will learn to detect these patterns
        registry.add_positive_example(
            code=code,
            vuln_type=detected_vuln,
            reasoning=f"Code contains potential {detected_vuln} vulnerability pattern",
            source=source_id,
        )

        count += 1

    logger.info("✅ Processing complete.")
    logger.info(f"   Total Vulnerable Examples Found: {count}")
    logger.info(f"   Total Files Scanned: {checked}")
    logger.info(f"   Skipped (Non-Python/Invalid Length): {skipped}")

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
